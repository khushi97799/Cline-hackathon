"""Deterministic next-question selector.

NOT an LLM. Picks, from the fields still missing in the profile, the one
that currently affects the largest number of candidate schemes' outcomes
(i.e. appears in the most rules among schemes not yet resolved to a final
outcome), and returns a single closed question using i18n keys only.

Stops (returns None) when no remaining missing field would change any
scheme's outcome -- i.e. every scheme is already likely_qualifies,
likely_not_eligible, or maybe_confirm_at_office for reasons unrelated to
missing data (only cant_tell is caused by missing data).
"""
from __future__ import annotations

from collections import Counter
from typing import Optional

from app.rules_engine import evaluate, missing_fields_for_rule, OUTCOME_CANT_TELL

# Field -> question spec. question_key / options are i18n keys resolved by
# the frontend/i18n layer; this module never hardcodes display text.
FIELD_QUESTIONS = {
    "age": {"question_key": "q_age", "input_type": "number_band",
            "options_key": "q_age_options"},
    "income_band": {"question_key": "q_income_band", "input_type": "choice",
                     "options_key": "q_income_band_options"},
    "income_amount": {"question_key": "q_income_amount", "input_type": "number_band",
                       "options_key": "q_income_amount_options"},
    "state": {"question_key": "q_state", "input_type": "choice", "options_key": "q_state_options"},
    "district": {"question_key": "q_district", "input_type": "choice", "options_key": "q_district_options"},
    "gender": {"question_key": "q_gender", "input_type": "choice", "options_key": "q_gender_options"},
    "occupation": {"question_key": "q_occupation", "input_type": "choice", "options_key": "q_occupation_options"},
    "caste_category": {"question_key": "q_caste_category", "input_type": "choice",
                        "options_key": "q_caste_category_options"},
    "marital_status": {"question_key": "q_marital_status", "input_type": "choice",
                        "options_key": "q_marital_status_options"},
    "family_size": {"question_key": "q_family_size", "input_type": "number_band",
                     "options_key": "q_family_size_options"},
    "land_holding": {"question_key": "q_land_holding", "input_type": "number_band",
                      "options_key": "q_land_holding_options"},
    "disability_status": {"question_key": "q_disability_status", "input_type": "choice",
                           "options_key": "q_disability_status_options"},
}


# Closed-question answer values (labels come from i18n keys "opt_<value>").
# Values match the vocabulary used in the rule files.
FIELD_OPTIONS = {
    "gender": ["female", "male", "other"],
    "occupation": ["farmer", "laborer", "self_employed", "salaried", "student", "homemaker", "other"],
    "income_band": ["BPL", "APL"],
    "caste_category": ["general", "obc", "sc", "st"],
    "marital_status": ["single", "married", "widowed", "divorced"],
    "disability_status": ["yes", "no"],
}


def _is_unresolved(rule: dict, profile: dict) -> bool:
    """A rule's outcome is 'unresolved' (could still change with more data)
    only if its current evaluation is cant_tell -- i.e. missing fields are
    actually blocking a hard-condition decision."""
    result = evaluate(rule, profile)
    return result.outcome == OUTCOME_CANT_TELL


def select_next_question(approved_rules: list, profile: dict) -> Optional[dict]:
    """Return the next question spec dict, or None if no field would
    change any scheme's outcome.

    approved_rules: list of approved rule dicts (one per scheme/state match)
    profile: dict of currently known field values
    """
    unresolved_rules = [r for r in approved_rules if _is_unresolved(r, profile)]
    if not unresolved_rules:
        return None

    field_counter: Counter = Counter()
    for rule in unresolved_rules:
        missing = missing_fields_for_rule(rule, profile)
        for f in missing:
            if f in FIELD_QUESTIONS:
                field_counter[f] += 1

    if not field_counter:
        return None

    best_field, _count = field_counter.most_common(1)[0]
    spec = dict(FIELD_QUESTIONS[best_field])
    spec["field"] = best_field
    if best_field in FIELD_OPTIONS:
        spec["options"] = list(FIELD_OPTIONS[best_field])
    return spec
