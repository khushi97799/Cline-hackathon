"""The whole 'a new scheme appears' journey, with the network and the LLM faked:
official page -> automatic draft -> admin checks -> live for citizens with its last date."""
import pytest

from app import discovery, rule_drafting, source_fetch
from app.routers import admin_sources
from app.source_fetch import FetchResult
from app.textutil import sha256_text
from tests.conftest import login
from tests.test_drafting_safety import PAGE, good_llm


@pytest.fixture(autouse=True)
def fake_network(monkeypatch):
    monkeypatch.setattr(source_fetch, "_resolve", lambda host: ["93.184.216.34"])
    monkeypatch.setattr(admin_sources, "fetch_source", lambda url: FetchResult(
        url, "Pradhan Test Yojana", PAGE, sha256_text(PAGE), "text/html", html=PAGE))
    real = rule_drafting.draft_scheme          # same code, but with the fake model instead of a real LLM
    fake = lambda sid, url, text, llm=None: real(sid, url, text, llm=good_llm)  # noqa: E731
    monkeypatch.setattr(admin_sources, "draft_scheme", fake)
    monkeypatch.setattr(discovery, "draft_scheme", fake)


def test_url_to_live_scheme(client):
    admin = login(client, "9000000009", "admin")
    r = client.post("/api/admin/ingest", json={"url": "https://newscheme.gov.in/pradhan-test"}, headers=admin)
    assert r.status_code == 200, r.text
    out = r.json()
    sid = out["scheme_id"]
    assert out["deadline_suggestion"]["date"] == "2030-12-31" and out["problems"] == []

    # 1. Draft: invisible to citizens.
    assert sid not in {s["scheme_id"] for s in client.get("/api/schemes").json()["schemes"]}
    assert client.get(f"/api/admin/schemes/{sid}/meta", headers=admin).json()["has_source"] is True

    # 2. Admin fills the filters and accepts the quoted last date found in the official text.
    cand = out["deadline_suggestion"]
    meta = {"level": "central", "state": "ALL", "tags": ["senior", "pension"], "category": "pension",
            "deadline_date": cand["date"], "deadline_quote": cand["quote"]}
    assert client.put(f"/api/admin/schemes/{sid}/meta", json=meta, headers=admin).status_code == 200

    # 3. Admin approves the drafted rule: schema, quotes in source and last date are re-checked.
    rules = client.get(f"/api/admin/rules/{sid}", headers=admin).json()["rule_versions"]
    assert [c["field"] for c in rules[0]["rule_json"]["conditions"]] == ["age", "income_band"]
    assert rules[0]["rule_json"]["conditions"][1]["type"] == "ambiguous"        # BPL
    ok = client.post("/api/admin/rules/review", json={"rule_version_id": rules[0]["id"], "approve": True}, headers=admin)
    assert ok.status_code == 200, ok.text

    # 4. Now it is live, filterable, with its deadline and the exact quote.
    live = {s["scheme_id"]: s for s in client.get("/api/schemes?tag=pension").json()["schemes"]}
    assert sid in live and live[sid]["verified"] is True
    assert live[sid]["deadline"]["date"] == "2030-12-31"
    assert live[sid]["deadline"]["quote"] == "The last date to apply is 31 December 2030."

    # 5. Citizens get a result from the rule engine (BPL is ambiguous, so never "likely").
    h = login(client, "9876500030", "citizen")
    pid = client.post("/api/persons", json={}, headers=h).json()["person_id"]
    for f, v in [("age", "65"), ("income_band", "bpl")]:
        client.post("/api/questions/answer", json={"person_id": pid, "field": f, "value": v}, headers=h)
    res = {x["scheme_id"]: x for x in client.get(f"/api/results/{pid}", headers=h).json()["results"]}
    assert res[sid]["outcome"] == "maybe_confirm_at_office" and res[sid]["deadline"]["state"] == "open"
