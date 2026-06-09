"""Step 1: use Claude to detect the source language (sql | spark | dbt)."""
from __future__ import annotations

import json
from dataclasses import dataclass

import anthropic

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


def detect_language(code: str, client: anthropic.Anthropic | None = None) -> Detection:
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
