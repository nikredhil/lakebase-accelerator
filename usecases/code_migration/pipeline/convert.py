"""Step 2: use Claude to convert source code -> Databricks PySpark `transform(spark)`.

Reads accumulated heuristics from SKILLS.md (injected into the prompt) and, on
validation failure, appends a concise learned lesson back to SKILLS.md so future
conversions improve without re-deriving the same gotchas (token-saving memory).
"""
from __future__ import annotations

import re

from accelerator.config import SKILLS_FILE
from usecases.code_migration.config import TABLE_SCHEMA
from usecases.code_migration.pipeline.reference_runner import render_dbt

MODEL = "claude-opus-4-8"

_FENCE = re.compile(r"^```(?:python)?\s*|\s*```$", re.MULTILINE)
_LESSON_MARK = "<!-- LESSONS-END -->"


def _skills() -> str:
    try:
        return SKILLS_FILE.read_text()
    except FileNotFoundError:
        return ""


def _system() -> str:
    return (
        "You convert SQL, dbt, or Spark code into a Databricks PySpark module.\n\n"
        "Follow these accumulated team heuristics EXACTLY:\n\n"
        f"{_skills()}\n\n"
        f"{TABLE_SCHEMA}\n"
        "Output ONLY the Python module text — no markdown fences, no commentary. "
        "It must define `def transform(spark):` returning a Spark DataFrame and "
        "must import pyspark functions it uses (e.g. `from pyspark.sql import functions as F`)."
    )


def _strip(code: str) -> str:
    return _FENCE.sub("", code).strip()


def _wrap_sql(sql: str) -> str:
    """Wrap a SQL query into a runnable transform(spark) (temp views pre-registered)."""
    sql = sql.strip().rstrip(";")
    return (
        "from pyspark.sql import DataFrame\n\n\n"
        "def transform(spark) -> DataFrame:\n"
        '    return spark.sql(\n        """\n'
        f"{sql}\n"
        '        """\n    )\n'
    )


def convert_rule(code: str, language: str) -> str:
    """Deterministic conversion — no API call.

    sql  -> spark.sql(<original>)         dbt -> spark.sql(<jinja rendered>)
    spark-> pass through (already a transform).
    """
    if language == "sql":
        return _wrap_sql(code)
    if language == "dbt":
        return _wrap_sql(render_dbt(code))
    if language == "spark":
        return code.strip()
    raise ValueError(f"rule converter cannot handle language {language!r}")


def convert(code: str, language: str, client=None, provider: str = "anthropic") -> str:
    if provider == "rule":
        return convert_rule(code, language)

    user = (
        f"Convert this {language} code into a Databricks PySpark `transform(spark)` module:\n\n"
        f"```\n{code}\n```"
    )

    if provider == "databricks":
        from usecases.code_migration.pipeline.llm import databricks_chat

        return _strip(databricks_chat(_system(), user, max_tokens=16000))

    import anthropic

    client = client or anthropic.Anthropic()
    with client.messages.stream(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=_system(),
        messages=[{"role": "user", "content": user}],
    ) as stream:
        msg = stream.get_final_message()
    text = next(b.text for b in msg.content if b.type == "text")
    return _strip(text)


def learn_lesson(original: str, converted: str, failure: str, client=None, provider: str = "anthropic") -> str:
    """Distill a one-line reusable lesson from a failed conversion and persist it."""
    system = (
        "A SQL/Spark/dbt -> PySpark conversion failed validation. Extract ONE "
        "concise, reusable, imperative lesson (max 25 words) that would prevent "
        "this class of error next time. Output only the lesson sentence."
    )
    user = f"ORIGINAL:\n{original}\n\nCONVERTED:\n{converted}\n\nVALIDATION FAILURE:\n{failure}"

    if provider == "databricks":
        from usecases.code_migration.pipeline.llm import databricks_chat

        lesson = databricks_chat(system, user, max_tokens=200).strip()
    else:
        import anthropic

        client = client or anthropic.Anthropic()
        resp = client.messages.create(
            model=MODEL, max_tokens=1000, thinking={"type": "adaptive"},
            system=system, messages=[{"role": "user", "content": user}],
        )
        lesson = next(b.text for b in resp.content if b.type == "text").strip()

    _append_lesson(lesson)
    return lesson


def _append_lesson(lesson: str) -> None:
    try:
        content = SKILLS_FILE.read_text()
    except FileNotFoundError:
        return
    if lesson in content:  # dedupe
        return
    bullet = f"- {lesson}\n"
    if _LESSON_MARK in content:
        content = content.replace(_LESSON_MARK, bullet + _LESSON_MARK)
    else:
        content += "\n" + bullet
    SKILLS_FILE.write_text(content)
