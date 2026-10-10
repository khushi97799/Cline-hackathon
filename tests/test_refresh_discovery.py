"""Daily refresh and discovery of new schemes (network is faked)."""
import pytest

from app import source_fetch
from app.daily_refresh import run_daily_refresh
from app.database import SessionLocal
from app.models import ChangeTicket, RuleVersion, Scheme, SchemeSource
from app.source_fetch import FetchResult, SourceFetchError
from app.sourcestore import save_source_text
from app.textutil import sha256_text
from tests.test_drafting_safety import PAGE, good_llm


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    """The URL safety check looks up DNS; pretend every official host is public."""
    monkeypatch.setattr(source_fetch, "_resolve", lambda host: ["93.184.216.34"])


def fake_fetcher(pages):
    def fetch(url):
        if url not in pages:           # a source left over from another test: behave like a dead site
            raise SourceFetchError("not reachable in this test")
        v = pages[url]
        if isinstance(v, Exception):
            raise v
        return FetchResult(url, "Title", v, sha256_text(v), "text/html", html=v)
    return fetch


def _watch(db, sid, text, url):
    save_source_text(sid, text)
    db.add(Scheme(scheme_id=sid, name="T " + sid, benefit="b", status="approved", data_json={"source": {"url": url}}))
    db.add(SchemeSource(scheme_id=sid, url=url, kind="page", last_hash=sha256_text(text)))
    db.commit()


def test_refresh_unchanged_changed_and_broken_site():
    db = SessionLocal()
    try:
        for sid, url in (("rf-same", "https://same.gov.in/"), ("rf-changed", "https://changed.gov.in/"),
                         ("rf-down", "https://down.gov.in/")):
            _watch(db, sid, PAGE, url)
        pages = {"https://same.gov.in/": PAGE,
                 "https://changed.gov.in/": PAGE.replace("31 December 2030", "31 March 2031"),
                 "https://down.gov.in/": SourceFetchError("The website answered with error 500.")}
        out = {s["scheme_id"]: s for s in run_daily_refresh(db, fetcher=fake_fetcher(pages), llm=good_llm, discover=False)
               if (s.get("scheme_id") or "").startswith("rf-")}
        assert out["rf-same"]["changed"] is False
        assert out["rf-changed"]["changed"] is True
        assert out["rf-down"]["changed"] is False and "error" in out["rf-down"]

        db.expire_all()
        assert db.get(Scheme, "rf-same").status == "approved"
        assert db.get(Scheme, "rf-down").status == "approved"            # a dead website changes nothing
        assert db.get(Scheme, "rf-changed").status == "needs_update"
        t = db.query(ChangeTicket).filter(ChangeTicket.scheme_id == "rf-changed").one()
        assert t.status == "open"
        draft = db.get(RuleVersion, t.draft_rule_version_id)
        assert draft.status == "draft" and draft.verified is False
    finally:
        db.close()


def test_changed_last_date_is_flagged_for_the_admin():
    db = SessionLocal()
    try:
        _watch(db, "rf-date", PAGE, "https://date.gov.in/")
        s = db.get(Scheme, "rf-date")
        s.deadline_json = {"date": "2030-12-31", "quote": "The last date to apply is 31 December 2030."}
        db.commit()
        pages = {"https://date.gov.in/": PAGE.replace("31 December 2030", "31 March 2031")}
        run_daily_refresh(db, fetcher=fake_fetcher(pages), llm=good_llm, discover=False)
        t = db.query(ChangeTicket).filter(ChangeTicket.scheme_id == "rf-date").one()
        assert "2031-03-31" in t.note and "2030-12-31" in t.note
    finally:
        db.close()


def test_discovery_creates_only_drafts_from_official_links():
    db = SessionLocal()
    try:
        db.add(SchemeSource(url="https://list.gov.in/schemes", kind="page", scheme_id=None))
        db.commit()
        listing = ('<a href="/new-yojana">Pradhan Test Yojana for farmers</a>'
                   '<a href="https://evil.example.com/x">Fake Scheme Offer yojana</a><a href="/contact">Contact us</a>')
        fetch = fake_fetcher({"https://list.gov.in/schemes": listing, "https://list.gov.in/new-yojana": PAGE})
        out = run_daily_refresh(db, fetcher=fetch, llm=good_llm)
        new = [s for s in out if s.get("new")]
        assert len(new) == 1
        s = db.get(Scheme, new[0]["scheme_id"])
        assert s.status == "draft"                                       # never public until an admin approves
        assert db.query(RuleVersion).filter(RuleVersion.scheme_id == s.scheme_id).one().verified is False
        again = run_daily_refresh(db, fetcher=fetch, llm=good_llm)       # second run: nothing new
        assert not [x for x in again if x.get("new")]
    finally:
        db.close()
