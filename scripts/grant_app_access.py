"""Grant the Lakebase Accelerator app's service principal the access its cost
center and live agent need. Run ONCE from an admin profile during rollout:

    python3 scripts/grant_app_access.py [--profile DEFAULT] [--app lakebase-accelerator]

It is idempotent and every grant is best-effort: failures are reported but do
not abort the others, and the app degrades gracefully without them (the cost
center falls back to rate-based estimates). Requires the running identity to be
a metastore admin (for system.billing) and able to manage the warehouse.
"""
from __future__ import annotations

import argparse
import sys
import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import (
    Disposition,
    Format,
    StatementState,
)


def _run_sql(w: WorkspaceClient, warehouse_id: str, sql: str) -> None:
    resp = w.statement_execution.execute_statement(
        statement=sql, warehouse_id=warehouse_id,
        disposition=Disposition.INLINE, format=Format.JSON_ARRAY, wait_timeout="30s",
    )
    deadline = time.time() + 60
    while resp.status and resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if time.time() > deadline:
            raise TimeoutError("statement timed out")
        time.sleep(2)
        resp = w.statement_execution.get_statement(resp.statement_id)
    if not resp.status or resp.status.state != StatementState.SUCCEEDED:
        msg = resp.status.error.message if resp.status and resp.status.error else "unknown"
        raise RuntimeError(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="DEFAULT")
    ap.add_argument("--app", default="lakebase-accelerator")
    ap.add_argument("--instance", default="lakebase-agent-backbone",
                    help="backbone instance to register the SP role on")
    args = ap.parse_args()

    w = WorkspaceClient(profile=args.profile)
    results: list[tuple[str, str]] = []

    # Identify the app service principal.
    sp = None
    try:
        app = w.apps.get(args.app)
        sp = app.service_principal_client_id
        print(f"app '{args.app}' SP client id: {sp}")
    except Exception as e:
        print(f"! could not read app '{args.app}': {e}")

    # Pick a warehouse to run GRANTs.
    wh = None
    try:
        whs = list(w.warehouses.list())
        wh = next((x.id for x in whs if getattr(x, "enable_serverless_compute", False)), None) \
            or (whs[0].id if whs else None)
    except Exception as e:
        print(f"! could not list warehouses: {e}")

    # 1) system.billing SELECT for the SP.
    if sp and wh:
        for stmt in (
            f"GRANT USE SCHEMA ON SCHEMA system.billing TO `{sp}`",
            f"GRANT SELECT ON SCHEMA system.billing TO `{sp}`",
        ):
            try:
                _run_sql(w, wh, stmt)
                results.append((stmt, "OK"))
            except Exception as e:
                results.append((stmt, f"FAILED: {str(e)[:120]}"))
    else:
        results.append(("GRANT system.billing", "SKIPPED (no SP or warehouse)"))

    # 2) Warehouse CAN_USE for the SP.
    if sp and wh:
        try:
            from databricks.sdk.service.sql import (
                WarehouseAccessControlRequest, WarehousePermissionLevel,
            )
            w.warehouses.update_permissions(
                wh,
                access_control_list=[WarehouseAccessControlRequest(
                    service_principal_name=sp,
                    permission_level=WarehousePermissionLevel.CAN_USE,
                )],
            )
            results.append((f"warehouse {wh} CAN_USE", "OK"))
        except Exception as e:
            results.append((f"warehouse {wh} CAN_USE", f"FAILED: {str(e)[:120]}"))

    # 3) Register BOTH app service principals as Postgres roles on the backbone
    #    instance. REQUIRED: each app authenticates to Lakebase Postgres as its
    #    own SP via an OAuth token; without a matching database role the login is
    #    rejected ("password authentication failed for user '<sp>'").
    #      - the agent app (lakebase-agent-backbone) connects to chat/persist.
    #      - the control-plane app (lakebase-accelerator) reads agent.interactions
    #        for the cost center's Agent bucket.
    #    Must be run by the instance owner / a metastore admin.
    try:
        from databricks.sdk.service.database import (
            DatabaseInstanceRole, DatabaseInstanceRoleIdentityType,
            DatabaseInstanceRoleMembershipRole,
        )
        w.database.get_database_instance(args.instance)  # exists?
        app_sps = {}
        for app_name in ("lakebase-agent-backbone", args.app):
            try:
                app_sps[app_name] = w.apps.get(app_name).service_principal_client_id
            except Exception:
                pass
        for app_name, app_sp in app_sps.items():
            if not app_sp:
                continue
            try:
                w.database.create_database_instance_role(
                    instance_name=args.instance,
                    database_instance_role=DatabaseInstanceRole(
                        name=app_sp,
                        identity_type=DatabaseInstanceRoleIdentityType.SERVICE_PRINCIPAL,
                        membership_role=DatabaseInstanceRoleMembershipRole.DATABRICKS_SUPERUSER,
                    ),
                )
                results.append((f"pg role for {app_name} on {args.instance}", "OK"))
            except Exception as e:
                results.append((f"pg role for {app_name} on {args.instance}", f"SKIPPED/FAILED: {str(e)[:90]}"))
    except Exception as e:
        results.append((f"pg roles on {args.instance}", f"SKIPPED/FAILED: {str(e)[:100]}"))

    print("\n=== grant results ===")
    for what, status in results:
        print(f"  [{status.split(':')[0]}] {what}")
    print("\nNote: failures are non-fatal — the cost center still renders estimates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
