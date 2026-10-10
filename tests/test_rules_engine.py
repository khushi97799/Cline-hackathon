import datetime as dt

import pytest
from hypothesis import given, strategies as st

from app.rules_engine import (
    evaluate,
    evaluate_rule,
    missing_fields_for_rule,
    OUTCOME_LIKELY_QUALIFIES,
    OUTCOME_MAYBE,
    OUTCOME_NOT_ELIGIBLE,
    OUTCOME_CANT_TELL,
)

SRC = {"url": "http://example.com", "page": 1, "clause": "1", "exact_quote": "quote"}


def make_rule(conditions, verified=True, review_by="2999-01-01"):
    return {
        "scheme_id": "test-scheme",
        "state": "ALL",
        "version": 1,
        "status": "approved",
        "verified": verified,
        "effective_from": "2020-01-01",
        "review_by": review_by,
        "source": SRC,
        "conditions": conditions,
    }


def cond(field, op, value, ctype="hard"):
    return {"field": field, "op": op, "value": value, "type": ctype, "source": SRC}


def test_all_hard_pass_verified_gives_likely_qualifies():
    rule = make_rule([cond("age", ">=", 18), cond("state", "=", "UP")])
    profile = {"age": 20, "state": "UP"}
    result = evaluate(rule, profile)
    assert result.outcome == OUTCOME_LIKELY_QUALIFIES


def test_unverified_rule_downgrades_likely_qualifies_to_maybe():
    rule = make_rule([cond("age", ">=", 18)], verified=False)
    profile = {"age": 30}
    result = evaluate(rule, profile)
    assert result.outcome == OUTCOME_MAYBE


def test_expired_review_by_downgrades_to_maybe():
    rule = make_rule([cond("age", ">=", 18)], verified=True, review_by="2000-01-01")
    profile = {"age": 30}
    result = evaluate(rule, profile)
    assert result.outcome == OUTCOME_MAYBE


def test_hard_condition_fail_gives_not_eligible():
    rule = make_rule([cond("age", ">=", 60)])
    profile = {"age": 30}
    result = evaluate(rule, profile)
    assert result.outcome == OUTCOME_NOT_ELIGIBLE


def test_hard_fail_wins_over_unverified_and_ambiguous():
    rule = make_rule(
        [cond("age", ">=", 60), cond("income", "<", 100000, ctype="ambiguous")],
        verified=False,
    )
    profile = {"age": 10, "income": 5000}
    result = evaluate(rule, profile)
    assert result.outcome == OUTCOME_NOT_ELIGIBLE


def test_missing_hard_field_gives_cant_tell():
    rule = make_rule([cond("age", ">=", 18)])
    profile = {}
    result = evaluate(rule, profile)
    assert result.outcome == OUTCOME_CANT_TELL


def test_ambiguous_condition_never_allows_likely_qualifies():
    rule = make_rule(
        [cond("age", ">=", 18), cond("category", "=", "BPL", ctype="ambiguous")]
    )
    profile = {"age": 30, "category": "BPL"}
    result = evaluate(rule, profile)
    assert result.outcome == OUTCOME_MAYBE


def test_ambiguous_unknown_also_gives_maybe_not_qualifies():
    rule = make_rule(
        [cond("age", ">=", 18), cond("category", "=", "BPL", ctype="ambiguous")]
    )
    profile = {"age": 30}
    result = evaluate(rule, profile)
    assert result.outcome == OUTCOME_MAYBE


def test_almost_eligible_when_exactly_one_hard_condition_fails():
    rule = make_rule(
        [cond("age", ">=", 60), cond("state", "=", "UP"), cond("income", "<", 100000)]
    )
    profile = {"age": 30, "state": "UP", "income": 50000}
    result = evaluate(rule, profile)
    assert result.outcome == OUTCOME_NOT_ELIGIBLE
    assert result.almost_eligible is True


def test_not_almost_eligible_when_two_hard_conditions_fail():
    rule = make_rule(
        [cond("age", ">=", 60), cond("state", "=", "UP"), cond("income", "<", 100000)]
    )
    profile = {"age": 30, "state": "MH", "income": 50000}
    result = evaluate(rule, profile)
    assert result.outcome == OUTCOME_NOT_ELIGIBLE
    assert result.almost_eligible is False


def test_boundary_equal_passes_gte():
    rule = make_rule([cond("age", ">=", 60)])
    profile = {"age": 60}
    result = evaluate(rule, profile)
    assert result.outcome == OUTCOME_LIKELY_QUALIFIES


def test_boundary_just_below_fails_gte():
    rule = make_rule([cond("age", ">=", 60)])
    profile = {"age": 59}
    result = evaluate(rule, profile)
    assert result.outcome == OUTCOME_NOT_ELIGIBLE


def test_in_operator():
    rule = make_rule([cond("state", "in", ["UP", "MH", "BR"])])
    assert evaluate(rule, {"state": "MH"}).outcome == OUTCOME_LIKELY_QUALIFIES
    assert evaluate(rule, {"state": "KA"}).outcome == OUTCOME_NOT_ELIGIBLE


def test_missing_fields_for_rule():
    rule = make_rule([cond("age", ">=", 18), cond("state", "=", "UP")])
    assert sorted(missing_fields_for_rule(rule, {})) == ["age", "state"]
    assert missing_fields_for_rule(rule, {"age": 20, "state": "UP"}) == []


# Property-based test: likely_qualifies must never occur when the rule has
# at least one ambiguous condition, regardless of profile values or whether
# the ambiguous field is known.
@given(
    age=st.integers(min_value=0, max_value=120),
    has_ambiguous_value=st.booleans(),
    ambiguous_value=st.text(min_size=1, max_size=5),
)
def test_property_ambiguous_condition_blocks_likely_qualifies(
    age, has_ambiguous_value, ambiguous_value
):
    rule = make_rule(
        [cond("age", ">=", 0), cond("category", "=", "BPL", ctype="ambiguous")]
    )
    profile = {"age": age}
    if has_ambiguous_value:
        profile["category"] = ambiguous_value
    result = evaluate(rule, profile)
    assert result.outcome != OUTCOME_LIKELY_QUALIFIES
