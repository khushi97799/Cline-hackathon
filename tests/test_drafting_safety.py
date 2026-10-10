"""What an LLM proposes is filtered by code; deadlines never come from the model."""
from app.draft_clean import clean_conditions
from app.rule_drafting import draft_scheme

PAGE = ("Pradhan Test Yojana.\n\nEligibility: The applicant must be 60 years of age or above.\n"
        "The applicant's household must belong to a BPL family.\n"
        "The last date to apply is 31 December 2030.\n")


def good_llm(text):
    return {"name": "Pradhan Test Yojana", "benefit": "Rs 500 a month", "category": "pension", "tags": ["senior"],
            "conditions": [
                {"field": "age", "op": ">=", "value": 60, "type": "hard", "exact_quote": "The applicant must be 60 years of age or above."},
                {"field": "income_band", "op": "=", "value": "BPL", "type": "hard",
                 "exact_quote": "The applicant's household must belong to a BPL family."}]}


def test_llm_output_is_filtered_by_code():
    bad = [
        {"field": "age", "op": ">=", "value": 60, "exact_quote": "The applicant must be 60 years of age or above."},
        {"field": "age", "op": ">=", "value": 70, "exact_quote": "Applicants must be 70 or older."},      # invented quote
        {"field": "aadhaar_number", "op": "=", "value": "1", "exact_quote": "The applicant must be 60"},  # banned field
        {"field": "age", "op": "~", "value": 1, "exact_quote": "The applicant must be 60"},               # bad operator
        {"field": "state", "op": "in", "value": "UP", "exact_quote": "The applicant must be 60"},         # 'in' needs a list
        {"field": "income_band", "op": "=", "value": "BPL", "type": "hard",
         "exact_quote": "The applicant's household must belong to a BPL family."},
    ]
    keep, problems = clean_conditions(bad, PAGE, "https://x.gov.in/")
    assert [c["field"] for c in keep] == ["age", "income_band"]
    assert len(problems) == 4
    assert keep[1]["type"] == "ambiguous"       # BPL is vague: forced to ambiguous although the model said hard


def test_draft_is_never_verified_and_deadline_comes_from_code():
    d = draft_scheme("pradhan-test-yojana", "https://x.gov.in/p", PAGE, llm=good_llm)
    r = d["rule"]
    assert r["status"] == "draft" and r["verified"] is False
    assert d["deadline_suggestion"] == {"date": "2030-12-31", "quote": "The last date to apply is 31 December 2030."}


def test_a_date_invented_by_the_model_is_ignored():
    def liar(text):
        out = good_llm(text)
        out["deadline"] = {"date": "2099-01-01", "quote": "Apply by 1 January 2099."}
        return out
    d = draft_scheme("s", "https://x.gov.in/p", PAGE, llm=liar)
    assert d["deadline_suggestion"]["date"] == "2030-12-31"


def test_a_broken_llm_falls_back_to_a_placeholder():
    def boom(text):
        raise RuntimeError("down")
    d = draft_scheme("s", "https://x.gov.in/p", PAGE, llm=boom)
    assert d["rule"]["conditions"][0]["field"] == "needs_manual_review" and d["problems"]
