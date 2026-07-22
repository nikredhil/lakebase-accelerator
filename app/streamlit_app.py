"""Lakebase Accelerator — Streamlit control plane (DAB-based).

A small, colorful UI over the DAB accelerator: set a use case's cost knobs, then
Plan / Deploy / Status / Destroy via the `lakebase` CLI, and watch live cluster +
warehouse state. Complements the in-workspace notebook control panel.

Run:  streamlit run app/streamlit_app.py     (from the repo root)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass

NODE_DEFAULTS = {"aws": "m5d.large", "azure": "Standard_DS3_v2", "gcp": "n2-standard-4"}
STATE_COLORS = {
    "RUNNING": "#2ea043", "PENDING": "#d29922", "RESIZING": "#d29922", "STARTING": "#d29922",
    "TERMINATING": "#bb8009", "TERMINATED": "#6e7681", "ERROR": "#f85149",
    "STOPPED": "#6e7681", "STARTED": "#2ea043", "DELETING": "#f85149", "UNKNOWN": "#6e7681",
}

st.set_page_config(page_title="Lakebase Accelerator", page_icon="🧱", layout="wide")


@st.cache_resource(show_spinner=False)
def _client():
    from databricks.sdk import WorkspaceClient

    return WorkspaceClient()


def badge(state: str) -> str:
    color = STATE_COLORS.get(str(state).upper(), "#6e7681")
    return (f"<span style='background:{color};color:white;padding:2px 10px;"
            f"border-radius:12px;font-size:0.8rem;font-weight:600'>{state}</span>")


def cli_cmd(action: str, name: str, target: str, overrides: dict | None = None, tags: str = "") -> list[str]:
    cmd = [sys.executable, "-m", "accelerator.cli", action, name]
    if action != "list":
        cmd += ["--target", target]
    if action in ("plan", "deploy"):
        for k, v in (overrides or {}).items():
            val = "true" if v is True else "false" if v is False else str(v)
            cmd += ["--var", f"{k}={val}"]
        if tags.strip():
            cmd += ["--tags", tags.strip()]
    return cmd


def run_stream(cmd: list[str], placeholder) -> int:
    lines: list[str] = []
    proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1, env=os.environ.copy())
    for line in proc.stdout:  # type: ignore[union-attr]
        lines.append(line.rstrip())
        placeholder.code("\n".join(lines[-300:]), language="bash")
    proc.wait()
    return proc.returncode


def fetch_compute():
    w = _client()
    clusters = [{
        "name": c.cluster_name, "state": c.state.value if c.state else "?",
        "id": c.cluster_id, "mode": c.data_security_mode.value if c.data_security_mode else "",
    } for c in w.clusters.list()]
    whs = [{
        "name": x.name, "state": str(x.state).split(".")[-1] if x.state else "?",
        "serverless": getattr(x, "enable_serverless_compute", None), "id": x.id,
    } for x in w.warehouses.list()]
    return clusters, whs


# ----------------------------------------------------------------- sidebar ----
with st.sidebar:
    st.markdown("### 🧱 Lakebase Accelerator")
    st.caption("DAB-based Databricks infra control plane")
    host = os.getenv("DATABRICKS_HOST", "")
    connected, who = False, ""
    try:
        who = _client().current_user.me().user_name
        connected = True
    except Exception as e:
        who = str(e)[:60]
    st.markdown(
        f"**Workspace**\n\n{host or '_not set_'}\n\n"
        f"{badge('CONNECTED') if connected else badge('ERROR')} &nbsp; "
        f"{who if connected else 'check DATABRICKS_HOST/TOKEN'}",
        unsafe_allow_html=True)
    st.divider()
    st.caption("This UI calls the `lakebase` CLI (DAB). It complements the in-workspace notebook panel.")


st.title("Lakebase Accelerator")
st.markdown(
    "Spin up and tear down cost-tuned Databricks infra for any use case — "
    "**a few clicks**, with <span style='color:#FF5F1F'>destroy</span> to stop billing.",
    unsafe_allow_html=True)

tab_deploy, tab_infra = st.tabs(["⚙️ Configure & Deploy", "📡 Live infra"])

# ------------------------------------------------------------- deploy tab -----
with tab_deploy:
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Use-case name", value="code_migration",
                             help="Isolates the DAB deployment + resources.")
        target = st.text_input("DAB target", value="dev")
        cloud = st.selectbox("Cloud", ["azure", "aws", "gcp"],
                            index=["azure", "aws", "gcp"].index(os.getenv("CLOUD", "azure")))
        node = st.text_input("Node type (blank = per-cloud default)", value="")
    with c2:
        single = st.toggle("Single node (cheapest: driver only)", value=False)
        spot = st.toggle("Spot / preemptible workers", value=True)
        max_workers = st.slider("Max workers", 1, 2, 2, disabled=single)
        autoterm = st.slider("Auto-terminate (idle min)", 5, 60, 20)
    tags = st.text_input("Custom tags (k=v,k=v)", value="", help="e.g. team=data,cost_center=1234")

    overrides: dict = {
        "cloud": cloud, "max_workers": max_workers, "single_node": single,
        "use_spot": spot, "autotermination_minutes": autoterm,
    }
    if node.strip():
        overrides["node_type_id"] = node.strip()

    eff_node = node.strip() or NODE_DEFAULTS[cloud]
    m1, m2, m3 = st.columns(3)
    m1.metric("Nodes", "1 (driver)" if single else f"1 + 1–{max_workers}")
    m2.metric("Node type", eff_node)
    m3.metric("Workers", "spot" if (spot and not single) else "on-demand")

    with st.expander("📄 Equivalent command", expanded=True):
        st.code("lakebase deploy " + name + " --target " + target + " " +
                " ".join(f"--var {k}={'true' if v is True else 'false' if v is False else v}"
                         for k, v in overrides.items()) +
                (f" --tags {tags}" if tags.strip() else ""), language="bash")

    st.divider()
    b1, b2, b3, b4 = st.columns(4)
    out = st.empty()

    if b1.button("🔍 Plan", use_container_width=True):
        with st.spinner("validating bundle…"):
            rc = run_stream(cli_cmd("plan", name, target, overrides, tags), out)
        (st.success if rc == 0 else st.error)(f"plan exit {rc}")

    if b2.button("📊 Status", use_container_width=True):
        with st.spinner("querying…"):
            rc = run_stream(cli_cmd("status", name, target), out)
        (st.success if rc == 0 else st.error)(f"status exit {rc}")

    confirm = b3.checkbox("confirm billable")
    if b3.button("🚀 Deploy", type="primary", use_container_width=True, disabled=not confirm):
        with st.spinner("deploying bundle… (cluster boot can take minutes)"):
            rc = run_stream(cli_cmd("deploy", name, target, overrides, tags), out)
        (st.success if rc == 0 else st.error)(f"deploy exit {rc}")

    if b4.button("🧨 Destroy", use_container_width=True):
        with st.spinner("destroying…"):
            rc = run_stream(cli_cmd("destroy", name, target), out)
        (st.success if rc == 0 else st.error)(f"destroy exit {rc} — billing stopped")

# -------------------------------------------------------------- infra tab -----
with tab_infra:
    st.caption("Live compute in the workspace. Spot workers + autotermination keep cost low.")
    cols = st.columns([1, 1, 4])
    if cols[0].button("🔄 Refresh"):
        st.cache_data.clear()
    if cols[1].button("📋 Deployments"):
        run_stream(cli_cmd("list", "", ""), st.empty())

    @st.cache_data(ttl=15, show_spinner="Querying workspace…")
    def _compute():
        return fetch_compute()

    try:
        clusters, whs = _compute()
        running = sum(1 for c in clusters if c["state"] in ("RUNNING", "PENDING"))
        k1, k2, k3 = st.columns(3)
        k1.metric("Clusters", len(clusters))
        k2.metric("Running / pending", running)
        k3.metric("SQL warehouses", len(whs))

        st.markdown("#### Clusters")
        if clusters:
            for c in clusters:
                st.markdown(f"{badge(c['state'])} &nbsp; **{c['name']}** "
                            f"<span style='color:#8b949e'>· {c['mode']} · `{c['id']}`</span>",
                            unsafe_allow_html=True)
        else:
            st.info("No clusters.")

        st.markdown("#### SQL warehouses")
        for x in whs:
            tag = " · serverless" if x["serverless"] else ""
            st.markdown(f"{badge(x['state'])} &nbsp; **{x['name']}**"
                        f"<span style='color:#8b949e'>{tag} · `{x['id']}`</span>",
                        unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Could not query workspace: {e}")

st.divider()
st.caption("Lakebase Accelerator · DAB · use cases plug in via --var/--vars-file overrides")
