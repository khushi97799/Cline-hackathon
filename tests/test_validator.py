import json

import pytest

from app.validator import quotes_exist_in_source, RuleValidationError, validate_rule, validate_schema

SRC = {"url": "http://example.com", "page": 1, "clause": "1", "exact_quote": "Eligible farmers must hold land."}


def make_rule(quote="Eligible farmers must hold land."):
    return {
        "scheme_id": "x",
        "state": "ALL",
        "version": 1,
        "status": "draft",
        "verified": False,
        "effective_from": "2020-01-01",
        "review_by": "2030-01-01",
        "source": {"url": "http://example.com", "page": 1, "clause": "1", "exact_quote": quote},
        "conditions": [
            {
                "field": "land_holding",
                "op": ">",
                "value": 0,
                "type": "hard",
                "source": {"url": "http://example.com", "page": 1, "clause": "1", "exact_quote": quote},
            }
        ],
    }


def test_valid_schema_passes():
    validate_schema(make_rule())


def test_invalid_op_fails_schema():
    rule = make_rule()
    rule["conditions"][0]["op"] = "~="
    with pytest.raises(RuleValidationError):
        validate_schema(rule)


def test_missing_required_field_fails_schema():
    rule = make_rule()
    del rule["review_by"]
    with pytest.raises(RuleValidationError):
        validate_schema(rule)


def test_quote_found_in_source_text():
    rule = make_rule()
    source_text = "Some preamble. Eligible farmers must hold land. Some footer."
    missing = quotes_exist_in_source(rule, source_text=source_text)
    assert missing == []


def test_quote_not_found_in_source_text():
    rule = make_rule(quote="This quote does not exist anywhere.")
    source_text = "Some preamble. Eligible farmers must hold land. Some footer."
    missing = quotes_exist_in_source(rule, source_text=source_text)
    assert len(missing) >= 1


def test_validate_rule_raises_when_quote_missing():
    rule = make_rule(quote="Fabricated quote not in source.")
    with pytest.raises(RuleValidationError):
        validate_rule(rule, source_text="Totally different source text.")


def test_validate_rule_passes_when_quote_present():
    rule = make_rule()
    validate_rule(rule, source_text="Preamble. Eligible farmers must hold land. End.")


def test_no_source_text_available_fails_safe():
    rule = make_rule()
    # No source_text provided and no file on disk for this scheme_id -> all quotes reported missing (fail-safe)
    missing = quotes_exist_in_source(rule, source_text=None)
    assert len(missing) >= 1
