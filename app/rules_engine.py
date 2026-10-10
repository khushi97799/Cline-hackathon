"""Deterministic eligibility rules engine.

NO LLM is involved in deciding eligibility. This module only reads
approved rule JSON (conforming to schema/rule.schema.json) and a profile
dict of known fields, and computes an outcome.

Outcomes:
  likely_qualifies          - all hard conditions pass, no ambiguous conditions,
                               rule is verified and not expired.
  maybe_confirm_at_office   - all hard conditions pass but either:
                                 - there is at least one ambiguous condition, or
                                 - the rule is unverified, or
                                 - the rule is past its review_by date
  likely_not_eligible       - at least one hard condition fails
  cant_tell                 - a hard condition cannot be evaluated because the
                               required profile field is missing, and no hard
                               condition has otherwise already failed.

Precedence: a definite hard-condition FAIL always wins and produces
likely_not_eligible, even if other fields are missing or ambiguous.

"almost eligible": set when exactly ONE hard condition fails and no other
hard condition is unknown (ambiguous conditions do not count toward this).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

OPS = {
    "=": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "in": lambda a, b: a in b,
}

OUTCOME_LIKELY_QUALIFIES = "likely_qualifies"
OUTCOME_MAYBE = "maybe_confirm_at_office"
OUTCOME_NOT_ELIGIBLE = "likely_not_eligible"
OUTCOME_CANT_TELL = "cant_tell"


@dataclass
class ConditionResult:
    field: str
    op: str
    value: Any
    type: str  # "hard" | "ambiguous"
    status: str  # "pass" | "fail" | "unknown"


@dataclass
class EvalResult:
    outcome: str
    almost_eligible: bool
    condition_results: list = field(default_factory=list)
    reasons: list = field(default_factory=list)


def _today() -> _dt.date:
    return _dt.date.today()


def _parse_date(s: str) -> _dt.date:
    return _dt.date.fromisoformat(s)


def evaluate_condition(cond: dict, profile: dict) -> ConditionResult:
    field_name = cond["field"]
    op = cond["op"]
    value = cond["value"]
    ctype = cond["type"]

    if field_name not in profile or profile[field_name] is None:
        return ConditionResult(field_name, op, value, ctype, "unknown")

    actual = profile[field_name]
    try:
        passed = OPS[op](actual, value)
    except TypeError:
        return ConditionResult(field_name, op, value, ctype, "unknown")

    return ConditionResult(field_name, op, value, ctype, "pass" if passed else "fail")


def evaluate_rule(rule: dict, profile: dict) -> EvalResult:
    """Evaluate a single approved rule against a profile dict.

    rule must be a dict already validated against schema/rule.schema.json.
    Caller is responsible for only calling this with approved rules for
    real citizen-facing results.
    """
    conditions = rule.get("conditions", [])
    results = [evaluate_condition(c, profile) for c in conditions]

    hard_results = [r for r in results if r.type == "hard"]
    ambiguous_results = [r for r in results if r.type == "ambiguous"]

    hard_fail_count = sum(1 for r in hard_results if r.status == "fail")
    hard_unknown = any(r.status == "unknown" for r in hard_results)
    ambiguous_unknown = any(r.status == "unknown" for r in ambiguous_results)
    has_ambiguous = len(ambiguous_results) > 0
    ambiguous_fail = any(r.status == "fail" for r in ambiguous_results)

    reasons: list = []
    almost_eligible = False

    if hard_fail_count >= 1:
        outcome = OUTCOME_NOT_ELIGIBLE
        reasons.append("One or more required conditions are not met.")
        if hard_fail_count == 1 and not hard_unknown:
            almost_eligible = True
        return EvalResult(outcome, almost_eligible, results, reasons)

    if hard_unknown:
        outcome = OUTCOME_CANT_TELL
        reasons.append("Not enough information to evaluate all required conditions.")
        return EvalResult(outcome, False, results, reasons)

    if ambiguous_fail or ambiguous_unknown or has_ambiguous:
        outcome = OUTCOME_MAYBE
        reasons.append("Some conditions depend on local/official confirmation.")
        return EvalResult(outcome, False, results, reasons)

    outcome = OUTCOME_LIKELY_QUALIFIES
    return EvalResult(outcome, False, results, reasons)


def apply_meta_downgrades(outcome: str, rule: dict, today=None):
    """Apply unverified / expired review_by downgrades.

    likely_qualifies is NEVER allowed to stand if the rule is unverified or
    past its review_by date; it is downgraded to maybe_confirm_at_office.
    """
    today = today or _today()
    reasons: list = []

    review_by = rule.get("review_by")
    expired = False
    if review_by:
        try:
            expired = today > _parse_date(review_by)
        except ValueError:
            expired = False

    verified = bool(rule.get("verified", False))

    if outcome == OUTCOME_LIKELY_QUALIFIES:
        if not verified:
            reasons.append("This scheme's rule has not yet been verified by an admin.")
            outcome = OUTCOME_MAYBE
        elif expired:
            reasons.append("This scheme's rule is past its review date and needs re-confirmation.")
            outcome = OUTCOME_MAYBE

    return outcome, reasons


def evaluate(rule: dict, profile: dict, today=None) -> EvalResult:
    """Full evaluation: condition logic + verified/expiry downgrade."""
    result = evaluate_rule(rule, profile)
    new_outcome, extra_reasons = apply_meta_downgrades(result.outcome, rule, today=today)
    result.outcome = new_outcome
    result.reasons.extend(extra_reasons)
    return result


def missing_fields_for_rule(rule: dict, profile: dict) -> list:
    """Return profile fields referenced by the rule that are missing."""
    missing = []
    for cond in rule.get("conditions", []):
        f = cond["field"]
        if f not in profile or profile[f] is None:
            if f not in missing:
                missing.append(f)
    return missing
