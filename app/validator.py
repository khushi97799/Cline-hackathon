"""Validate scheme rule JSON files against schema/rule.schema.json.

Rules:
- Must conform to JSON schema.
- Every condition's `source.exact_quote` must literally appear in the
  corresponding raw source text file (data/raw/<scheme_id>.txt) OR in the
  quote text supplied directly (for ingestion-time validation where the
  raw text is passed in).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from app.textutil import contains_normalized

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "rule.schema.json"
RAW_DIR = ROOT / "data" / "raw"


def load_schema() -> dict:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class RuleValidationError(Exception):
    pass


def validate_schema(rule: dict) -> None:
    schema = load_schema()
    try:
        jsonschema.validate(instance=rule, schema=schema)
    except jsonschema.ValidationError as e:
        raise RuleValidationError(f"Schema validation failed: {e.message}") from e


def _load_source_text(source_url: str, scheme_id: str) -> str | None:
    """Best-effort lookup of raw source text for a scheme.

    Looks for data/raw/<scheme_id>.txt first; falls back to scanning all
    .txt files in data/raw for a match containing the quote (handled by
    caller). Returns None if nothing found.
    """
    candidate = RAW_DIR / f"{scheme_id}.txt"
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    return None


def quotes_exist_in_source(rule: dict, source_text: str | None = None) -> list[str]:
    """Return list of quotes that could NOT be found in the source text.

    If source_text is None, attempts to load based on scheme_id from
    data/raw/. If still unavailable, all quotes are reported as missing
    (fail safe).
    """
    missing: list[str] = []
    scheme_id = rule.get("scheme_id", "")
    text = source_text if source_text is not None else _load_source_text(
        rule.get("source", {}).get("url", ""), scheme_id
    )

    # Also check top-level rule source quote
    top_quote = rule.get("source", {}).get("exact_quote", "")
    all_quotes = [top_quote] if top_quote else []
    for cond in rule.get("conditions", []):
        q = cond.get("source", {}).get("exact_quote", "")
        if q:
            all_quotes.append(q)

    if text is None:
        return all_quotes  # fail safe: nothing verifiable

    for q in all_quotes:
        if not contains_normalized(text, q):
            missing.append(q)
    return missing


def validate_rule(rule: dict, source_text: str | None = None) -> None:
    """Full validation: schema + quote provenance. Raises RuleValidationError."""
    validate_schema(rule)
    missing = quotes_exist_in_source(rule, source_text=source_text)
    if missing:
        raise RuleValidationError(
            "The following quotes were not found verbatim in the source text: "
            + " | ".join(missing)
        )


def validate_file(path: str | Path) -> dict:
    p = Path(path)
    with open(p, "r", encoding="utf-8") as f:
        rule = json.load(f)
    validate_rule(rule)
    return rule


if __name__ == "__main__":
    import sys

    for path in sys.argv[1:]:
        try:
            validate_file(path)
            print(f"OK: {path}")
        except RuleValidationError as e:
            print(f"FAIL: {path}: {e}")
            raise SystemExit(1)
