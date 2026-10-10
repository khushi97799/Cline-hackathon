"""Filters, sorting and deadlines in the public catalogue."""
import datetime as dt

from app.catalogue import matches, scheme_card, sort_cards
from app.models import Scheme


def card(name, tags=(), level="central", state="ALL", verified=True, deadline=None, category="x"):
    s = Scheme(scheme_id=name.lower(), name=name, benefit="b", category=category, status="approved", level=level,
               state=state, tags=list(tags), deadline_json=deadline, data_json={})
    return scheme_card(s, verified, dt.date(2026, 10, 10))


def test_filters_combine():
    a = card("Farmer Aid", ["farmer"], "central")
    b = card("Women Loan", ["women", "business"], "state", "Bihar")
    assert matches(a, tag="farmer") and not matches(b, tag="farmer")
    assert matches(b, level="state") and not matches(a, level="state")
    assert matches(b, state="Bihar") and matches(a, state="Bihar")       # national schemes apply in every state
    assert not matches(b, state="Kerala")
    assert matches(a, verified=True) and not matches(a, verified=False)


def test_deadline_filters_and_sorting():
    soon = card("Soon", deadline={"date": "2026-10-20", "quote": "q"})
    later = card("Later", deadline={"date": "2027-06-01", "quote": "q"})
    none = card("None")
    gone = card("Gone", deadline={"date": "2026-09-01", "quote": "q"})
    assert matches(soon, deadline="closing_soon") and not matches(later, deadline="closing_soon")
    assert matches(gone, deadline="closed") and not matches(gone, deadline="open")
    assert matches(none, deadline="no_deadline")
    assert [c["name"] for c in sort_cards([gone, none, later, soon], "deadline")] == ["Soon", "Later", "None", "Gone"]
    assert sort_cards([gone, soon], "relevance")[-1]["name"] == "Gone"        # closed always last


def test_unverified_scheme_ranks_after_verified_ones():
    ok, unverified = card("A-ok"), card("B-new", verified=False)
    assert [c["name"] for c in sort_cards([unverified, ok], "relevance")] == ["A-ok", "B-new"]
