"""Checks applied to anything an LLM proposes. Pure code, no model involved.

- Only known field names and operators are accepted.
- Every condition needs an exact quote found word-for-word in the source text.
- Vague wording (BPL, poor, needy ...) is forced to "ambiguous" whatever the model said.
"""
from __future__ import annotations

import re

from app.textutil import contains_normalized, normalize_ws

ALLOWED_FIELDS = {"age", "gender", "state", "district", "occupation", "income_band", "income_amount",
                  "caste_category", "marital_status", "family_size", "land_holding", "disability_status"}
ALLOWED_OPS = {"=", "!=", "<", "<=", ">", ">=", "in"}
VAGUE = re.compile(
    r"\b(bpl|below poverty|poverty line|poor|needy|deserving|vulnerable|marginali[sz]ed|"
    r"economically weak|ews|low[- ]income|eligible as per|as per (?:the )?(?:state|criteria|norms)|"
    r"as determined by|may be)\b", re.I)


def source_ref(url: str, quote: str) -> dict:
    return {"url": url, "page": 1, "clause": "auto-draft", "exact_quote": quote}


def clean_conditions(raw: list, source_text: str, url: str):
    """Keep only well-formed conditions whose quote exists in the source.
    Returns (conditions, problems)."""
    keep, problems = [], []
    for c in raw or []:
        if not isinstance(c, dict):
            continue
        field, op, quote = c.get("field"), c.get("op"), normalize_ws(str(c.get("exact_quote", "")))
        if field not in ALLOWED_FIELDS or op not in ALLOWED_OPS or "value" not in c:
            problems.append(f"Dropped a condition with an unsupported field/operator: {field} {op}")
            continue
        if op == "in" and not isinstance(c["value"], list):
            problems.append(f"Dropped '{field} in ...' because the value is not a list.")
            continue
        if not quote or not contains_normalized(source_text, quote):
            problems.append(f"Dropped '{field} {op} {c['value']}' because its quote is not in the source.")
            continue
        vague = c.get("type") == "ambiguous" or VAGUE.search(quote) or VAGUE.search(str(c["value"]))
        item = {"field": field, "op": op, "value": c["value"], "type": "ambiguous" if vague else "hard",
                "source": source_ref(url, quote)}
        if c.get("note"):
            item["note"] = str(c["note"])[:300]
        keep.append(item)
    return keep, problems
