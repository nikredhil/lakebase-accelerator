"""Step 1: detect the source language (sql | spark | dbt).

Two providers:
  - "anthropic": Claude classifies (production).
  - "rule":      deterministic regex rules (demo / no API spend).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

MODEL = "claude-opus-4-8"

_SCHEMA = {
    "type": "object",
    "properties": {
        "language": {"type": "string", "enum": ["sql", "spark", "dbt", "unknown"]},
        "confidence": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["language", "confidence", "reasoning"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You classify a data-pipeline code snippet as one of: sql, spark, dbt, unknown.\n"
    "- dbt: SQL containing Jinja such as {{ ref(...) }}, {{ source(...) }}, or {{ config(...) }}.\n"
    "- spark: Python using a SparkSession / DataFrame API (pyspark).\n"
    "- sql: plain SQL with no Jinja.\n"
    "Return your classification via the required JSON schema."
)


@dataclass
class Detection:
    language: str
    confidence: float
    reasoning: str


def detect_language_rule(code: str) -> Detection:
    """Deterministic detection — no API call."""
    if re.search(r"{{.*?\b(ref|source|config)\s*\(", code, re.S):
        return Detection("dbt", 1.0, "Contains dbt Jinja (ref/source/config).")
    if re.search(r"\b(SparkSession|pyspark|spark\.)|def\s+transform\s*\(", code):
        return Detection("spark", 1.0, "Uses the Spark / PySpark API.")
    if re.search(r"\bSELECT\b", code, re.I):
        return Detection("sql", 0.9, "Plain SQL with no Jinja templating.")
    return Detection("unknown", 0.3, "No clear language signal.")


def detect_language(code: str, client=None, provider: str = "anthropic") -> Detection:
    if provider == "rule":
        return detect_language_rule(code)

    if provider == "databricks":
        from usecases.code_migration.pipeline.llm import databricks_chat

        out = databricks_chat(
            _SYSTEM + "\nRespond with ONLY one word: sql, dbt, spark, or unknown.",
            f"Classify this code:\n\n```\n{code}\n```",
            max_tokens=20,
        )
        lang = out.strip().lower().split()[0].strip(".,`") if out.strip() else "unknown"
        if lang not in ("sql", "dbt", "spark", "unknown"):
            lang = "unknown"
        return Detection(lang, 0.9, "Databricks-hosted Claude classification.")

    import anthropic

    client = client or anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"Classify this code:\n\n```\n{code}\n```"}],
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
    )
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)
    return Detection(data["language"], float(data["confidence"]), data["reasoning"])
