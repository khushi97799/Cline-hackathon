import datetime as dt

from app.deadlines import (
    deadline_status, extract_deadline_candidates, find_dates, pick_deadline, validate_deadline,
)
from app.textutil import contains_normalized, sentence_around

SRC = """Scheme guidelines.

Eligibility: the applicant must be 60 years of age or above.
The last date to apply is 31 December 2026. Late forms are not accepted.
Valid till 15/08/2030 for existing members.
"""


def test_finds_dates_in_many_written_forms():
    got = {d for d, _, _ in find_dates("31 Dec 2026, 1st March 2027, April 5, 2028, 07/09/2029, 2030-01-02, 31 फरवरी 2026")}
    assert dt.date(2026, 12, 31) in got and dt.date(2027, 3, 1) in got and dt.date(2028, 4, 5) in got
    assert dt.date(2029, 9, 7) in got and dt.date(2030, 1, 2) in got   # numeric dates are day-first
    assert not any(d.month == 2 and d.day == 31 for d in got)          # impossible dates are ignored


def test_only_last_date_wording_counts_as_a_deadline():
    cands = extract_deadline_candidates(SRC)
    assert [c["date"] for c in cands] == ["2026-12-31"]                 # "valid till" is NOT a deadline
    assert contains_normalized(SRC, cands[0]["quote"])


def test_quote_is_an_exact_sentence_from_the_source():
    c = extract_deadline_candidates(SRC)[0]
    assert c["quote"] == "The last date to apply is 31 December 2026."


def test_wrapped_lines_do_not_break_the_sentence():
    text = "Applications must be submitted before\n31 March 2027 through the portal."
    assert [c["date"] for c in extract_deadline_candidates(text)] == ["2027-03-31"]


def test_hindi_wording():
    text = "आवेदन की अंतिम तिथि 15 जून 2027 है।"
    assert [c["date"] for c in extract_deadline_candidates(text)] == ["2027-06-15"]


def test_no_cue_no_deadline():
    assert extract_deadline_candidates("The scheme launched on 1 April 2020 and covers all farmers.") == []


def test_auto_pick_only_when_exactly_one_date():
    two = "Last date to apply is 1 May 2027. Last date for appeals is 1 June 2027."
    assert pick_deadline(extract_deadline_candidates(two)) is None
    assert pick_deadline(extract_deadline_candidates(SRC))["date"] == "2026-12-31"


def test_validation_blocks_wrong_or_invented_deadlines():
    good = {"date": "2026-12-31", "quote": "The last date to apply is 31 December 2026."}
    assert validate_deadline(good, SRC) == []
    assert validate_deadline({"date": "2027-01-31", "quote": good["quote"]}, SRC)              # date not in quote
    assert validate_deadline({"date": "2026-12-31", "quote": "Apply by 31 December 2026."}, SRC)  # quote not in source
    assert validate_deadline({"date": "2026-12-31", "quote": ""}, SRC)                         # no quote
    assert validate_deadline({"date": "not-a-date", "quote": good["quote"]}, SRC)
    assert validate_deadline(good, "") != []


def test_status_boundaries():
    today = dt.date(2026, 10, 10)
    assert deadline_status(None, today)["state"] == "open_ended"
    assert deadline_status({"date": "2026-10-09"}, today)["state"] == "closed"
    last = deadline_status({"date": "2026-10-10"}, today)
    assert last["state"] == "closing_soon" and last["days_left"] == 0      # the last day still counts
    assert deadline_status({"date": "2026-11-09"}, today)["state"] == "closing_soon"   # 30 days
    assert deadline_status({"date": "2026-11-10"}, today)["state"] == "open"           # 31 days
    assert deadline_status({"date": "garbage"}, today)["state"] == "open_ended"


def test_sentence_helper_never_returns_text_that_is_not_in_the_source():
    text = "A. " + "word " * 300 + "last date 5 May 2027 " + "word " * 300 + "."
    s, e = text.index("5 May"), text.index("5 May") + 9
    q = sentence_around(text, s, e)
    assert q in text and len(q) <= 420 and "5 May 2027" in q
