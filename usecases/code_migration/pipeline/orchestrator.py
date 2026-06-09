"""End-to-end pipeline for one example (the whiteboard flow):

  detect language -> convert -> run candidate on sample -> run reference on sample
  -> compare -> (pass) raise PR | (fail) learn lesson into SKILLS.md and retry.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import anthropic

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


def run_example(
    example: Example,
    candidate_backend: str = "local",
    max_retries: int = 3,
    raise_pull_request: bool = True,
    pr_dry_run: bool = True,
    client: anthropic.Anthropic | None = None,
) -> ExampleResult:
    client = client or anthropic.Anthropic()
    result = ExampleResult(example=example.key)
    source = example.path.read_text()
    tables = generate_mock_data.load_sample()  # small sample, shared by both runs

    # Step 1: detect
    det = detect.detect_language(source, client=client)
    result.detected_language = det.language
    language = det.language if det.language != "unknown" else example.expected_language

    # Reference result is computed once from the original code.
    reference = reference_runner.run_reference(
        language, source, example.path, tables, spark_backend=candidate_backend
    )

    converted = ""
    failure = ""
    for attempt in range(1, max_retries + 1):
        result.attempts = attempt
        # Step 2: convert (prompt includes SKILLS.md, which grows on each failure)
        converted = convert.convert(source, language, client=client)
        try:
            # Step 3 + 4: run candidate on the sample, compare to reference
            candidate = databricks_runner.run_candidate(converted, tables, backend=candidate_backend)
            cmp = compare.compare(reference, candidate)
            failure = cmp.detail
            if cmp.ok:
                result.passed = True
                result.detail = cmp.detail
                break
        except Exception as exc:  # candidate failed to execute -> treat as validation failure
            failure = f"Candidate execution error: {exc}"

        # Step 6: learn from the failure, then retry
        lesson = convert.learn_lesson(source, converted, failure, client=client)
        result.lessons.append(lesson)
        result.detail = failure

    # Step 5: PR on success
    if result.passed and raise_pull_request:
        pr_res = pr.raise_pr(example.key, converted, summary=result.detail, dry_run=pr_dry_run)
        result.pr_detail = pr_res.detail
    elif result.passed:
        out = pr.write_converted(example.key, converted)
        result.pr_detail = f"PR skipped; converted file written to {out}"

    return result
