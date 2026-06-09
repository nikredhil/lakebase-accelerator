"""End-to-end pipeline for one example (the whiteboard flow):

  detect language -> convert -> run candidate on sample -> run reference on sample
  -> compare -> (pass) raise PR | (fail) learn lesson into SKILLS.md and retry.

Each run is logged to MLflow (params, metrics, converted-code artifact, lessons)
and each step is wrapped in an MLflow trace span — viewable in the workspace MLflow
UI. All MLflow calls degrade to no-ops if MLflow/credentials are unavailable.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

from accelerator.config import SETTINGS
from usecases.code_migration.config import Example
from usecases.code_migration.data import generate_mock_data
from usecases.code_migration.pipeline import compare, convert, databricks_runner, detect, pr, reference_runner


@dataclass
class ExampleResult:
    example: str
    detected_language: str = ""
    attempts: int = 0
    passed: bool = False
    detail: str = ""
    lessons: list[str] = field(default_factory=list)
    pr_detail: str = ""


# --- MLflow plumbing (optional / graceful) -------------------------------------
def _mlflow():
    if not SETTINGS.mlflow_enabled:
        return None
    try:
        import mlflow

        mlflow.set_tracking_uri(SETTINGS.mlflow_tracking_uri)
        exp = SETTINGS.mlflow_experiment
        if not exp:
            from databricks.sdk import WorkspaceClient

            exp = f"/Users/{WorkspaceClient().current_user.me().user_name}/lakebase_code_migration"
        mlflow.set_experiment(exp)
        return mlflow
    except Exception as e:  # missing mlflow, no creds, etc. -> run without observability
        print(f"  [mlflow disabled: {e}]")
        return None


@contextlib.contextmanager
def _span(mlf, name: str):
    if mlf is None:
        yield None
        return
    try:
        with mlf.start_span(name=name) as s:
            yield s
    except Exception:
        yield None


def run_example(
    example: Example,
    candidate_backend: str = "local",
    max_retries: int = 3,
    raise_pull_request: bool = True,
    pr_dry_run: bool = True,
    provider: str = "anthropic",
    client=None,
) -> ExampleResult:
    if provider == "anthropic" and client is None:
        import anthropic

        client = anthropic.Anthropic()
    if provider in ("rule",):
        max_retries = 1  # deterministic; retrying an identical conversion is pointless

    mlf = _mlflow()
    run_cm = mlf.start_run(run_name=f"{example.key}-{provider}-{candidate_backend}") if mlf else contextlib.nullcontext()

    result = ExampleResult(example=example.key)
    source = example.path.read_text()
    tables = generate_mock_data.load_sample()

    with run_cm:
        if mlf:
            mlf.log_params({"example": example.key, "provider": provider,
                            "candidate_backend": candidate_backend, "max_retries": max_retries})
            mlf.log_text(source, "source.txt")

        # Step 1: detect
        with _span(mlf, "detect"):
            det = detect.detect_language(source, client=client, provider=provider)
        result.detected_language = det.language
        language = det.language if det.language != "unknown" else example.expected_language
        if mlf:
            mlf.set_tags({"detected_language": det.language, "language_used": language})

        # Reference result (original code, independent engine), computed once.
        with _span(mlf, "reference_run"):
            reference = reference_runner.run_reference(
                language, source, example.path, tables, spark_backend=candidate_backend
            )

        converted = ""
        failure = ""
        for attempt in range(1, max_retries + 1):
            result.attempts = attempt
            with _span(mlf, f"convert.attempt{attempt}"):
                converted = convert.convert(source, language, client=client, provider=provider)
            try:
                with _span(mlf, f"candidate_run.attempt{attempt}"):
                    candidate = databricks_runner.run_candidate(converted, tables, backend=candidate_backend)
                with _span(mlf, f"compare.attempt{attempt}"):
                    cmp = compare.compare(reference, candidate)
                failure = cmp.detail
                if cmp.ok:
                    result.passed = True
                    result.detail = cmp.detail
                    break
            except Exception as exc:
                failure = f"Candidate execution error: {exc}"

            result.detail = failure
            if provider in ("anthropic", "databricks"):
                with _span(mlf, f"learn.attempt{attempt}"):
                    lesson = convert.learn_lesson(source, converted, failure, client=client, provider=provider)
                result.lessons.append(lesson)

        # Step 5: PR on success
        if result.passed and raise_pull_request:
            with _span(mlf, "raise_pr"):
                pr_res = pr.raise_pr(example.key, converted, summary=result.detail, dry_run=pr_dry_run)
            result.pr_detail = pr_res.detail
        elif result.passed:
            out = pr.write_converted(example.key, converted)
            result.pr_detail = f"PR skipped; converted file written to {out}"

        if mlf:
            mlf.log_text(converted, "converted_transform.py")
            mlf.log_metrics({"attempts": result.attempts, "passed": int(result.passed),
                             "reference_rows": int(reference.shape[0])})
            mlf.set_tags({"result": "PASS" if result.passed else "FAIL"})
            if result.lessons:
                mlf.log_text("\n".join(result.lessons), "lessons.txt")

    return result
