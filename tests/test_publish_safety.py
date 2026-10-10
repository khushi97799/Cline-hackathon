"""Things an admin or an attacker must NOT be able to do."""
import httpx
import pytest

from app import discovery, rule_drafting, source_fetch
from app.database import SessionLocal
from app.models import RuleVersion, Scheme
from app.routers import admin_sources
from tests.conftest import login
from tests.test_drafting_safety import PAGE, good_llm


@pytest.fixture(autouse=True)
def fake_network(monkeypatch):
    monkeypatch.setattr(source_fetch, "_resolve", lambda host: ["93.184.216.34"])
    real_fetch = source_fetch.fetch_source     # the REAL fetcher, so URL validation really runs
    page = httpx.MockTransport(lambda r: httpx.Response(200, text=PAGE, headers={"content-type": "text/plain"}))
    monkeypatch.setattr(admin_sources, "fetch_source", lambda url: real_fetch(url, transport=page))
    real = rule_drafting.draft_scheme
    fake = lambda sid, url, text, llm=None: real(sid, url, text, llm=good_llm)  # noqa: E731
    monkeypatch.setattr(admin_sources, "draft_scheme", fake)
    monkeypatch.setattr(discovery, "draft_scheme", fake)


def test_cannot_approve_a_forged_quote_or_a_mismatched_deadline(client):
    admin = login(client, "9000000009", "admin")
    sid = client.post("/api/admin/ingest", json={"url": "https://other.gov.in/safety"}, headers=admin).json()["scheme_id"]
    version = client.get(f"/api/admin/rules/{sid}", headers=admin).json()["rule_versions"][0]

    forged = version["rule_json"]
    forged["conditions"][0]["source"]["exact_quote"] = "Everyone above 18 qualifies."
    r = client.post("/api/admin/rules/review", headers=admin,
                    json={"rule_version_id": version["id"], "approve": True, "edited_rule_json": forged})
    assert r.status_code == 400 and "verbatim" in r.json()["detail"]

    db = SessionLocal()
    try:
        db.get(Scheme, sid).deadline_json = {"date": "2031-01-01", "quote": "The last date to apply is 31 December 2030."}
        db.commit()
    finally:
        db.close()
    r = client.post("/api/admin/rules/review", json={"rule_version_id": version["id"], "approve": True}, headers=admin)
    assert r.status_code == 400 and "Last date" in r.json()["detail"]


def test_ingest_rejects_non_official_and_internal_urls(client):
    admin = login(client, "9000000009", "admin")
    for bad in ("https://example.com/scheme", "http://127.0.0.1/admin", "file:///etc/passwd"):
        assert client.post("/api/admin/ingest", json={"url": bad}, headers=admin).status_code == 400
    assert client.post("/api/admin/ingest", json={"url": "https://newscheme.gov.in/x"}).status_code == 401
    citizen = login(client, "9876500031", "citizen")
    assert client.post("/api/admin/ingest", json={"url": "https://newscheme.gov.in/x"}, headers=citizen).status_code == 403


def test_a_new_draft_for_a_live_scheme_does_not_replace_the_approved_rule(client):
    admin = login(client, "9000000009", "admin")
    text = open("data/raw/pm-kisan.txt", encoding="utf-8").read()
    assert client.post("/api/admin/ingest", json={"scheme_id": "pm-kisan", "text": text}, headers=admin).status_code == 200
    db = SessionLocal()
    try:
        q = db.query(RuleVersion).filter(RuleVersion.scheme_id == "pm-kisan")
        assert q.filter(RuleVersion.status == "approved").count() == 1       # citizens still see the approved one
        assert q.filter(RuleVersion.status == "draft").count() >= 1
    finally:
        db.close()
