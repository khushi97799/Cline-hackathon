"""The catalogue and the admin publish rules, through the real API."""
from app.database import SessionLocal
from app.models import Scheme
from app.sourcestore import load_source_text, save_source_text
from tests.conftest import login


def _admin(client):
    return login(client, "9000000009", "admin")


def test_public_catalogue_has_tags_levels_and_deadline(client):
    d = client.get("/api/schemes").json()
    assert "farmer" in d["tags"] and d["levels"] == ["central", "state"]
    kisan = next(s for s in d["schemes"] if s["scheme_id"] == "pm-kisan")
    assert kisan["level"] == "central" and kisan["deadline"]["state"] == "open_ended"
    assert [s["scheme_id"] for s in client.get("/api/schemes?tag=senior").json()["schemes"]] == ["nsap-pension"]
    assert client.get("/api/schemes?tag=nonexistent").json()["schemes"] == []


def test_deadline_needs_a_matching_quote_to_be_saved(client):
    h = _admin(client)
    fake = {"tags": ["farmer"], "level": "central", "deadline_date": "2026-12-31",
            "deadline_quote": "The last date to apply is 31 December 2026."}
    r = client.put("/api/admin/schemes/pm-kisan/meta", json=fake, headers=h)   # not in pm-kisan's official text
    assert r.status_code == 400 and "word-for-word" in r.json()["detail"]
    clear = {**fake, "deadline_date": "", "deadline_quote": ""}
    assert client.put("/api/admin/schemes/pm-kisan/meta", json=clear, headers=h).status_code == 200
    assert client.put("/api/admin/schemes/pm-kisan/meta", json={"tags": ["nonsense"]}, headers=h).status_code == 400


def test_a_real_quoted_deadline_is_saved_and_shown(client):
    h = _admin(client)
    original = load_source_text("pm-ujjwala")
    try:
        save_source_text("pm-ujjwala", original + "\nThe last date to apply is 31 December 2099.\n")
        body = {"tags": ["women"], "level": "central", "deadline_date": "2099-12-31",
                "deadline_quote": "The last date to apply is 31 December 2099."}
        assert client.put("/api/admin/schemes/pm-ujjwala/meta", json=body, headers=h).status_code == 200
        detail = client.get("/api/schemes/pm-ujjwala").json()
        assert detail["deadline"]["date"] == "2099-12-31" and detail["deadline"]["state"] == "open"
        assert detail["deadline"]["quote"].endswith("31 December 2099.")
        meta = client.get("/api/admin/schemes/pm-ujjwala/meta", headers=h).json()
        assert meta["deadline_candidates"][0]["date"] == "2099-12-31"
    finally:
        save_source_text("pm-ujjwala", original)
        client.put("/api/admin/schemes/pm-ujjwala/meta", json={"tags": ["women", "energy"], "level": "central"}, headers=h)


def _citizen_with_farm(client, phone):
    h = login(client, phone, "citizen")
    pid = client.post("/api/persons", json={}, headers=h).json()["person_id"]
    for f, v in [("occupation", "farmer"), ("land_holding", "2")]:
        client.post("/api/questions/answer", json={"person_id": pid, "field": f, "value": v}, headers=h)
    return h, pid


def _kisan(client, h, pid):
    return next(x for x in client.get(f"/api/results/{pid}", headers=h).json()["results"] if x["scheme_id"] == "pm-kisan")


def test_closed_deadline_is_visible_in_results(client):
    h, pid = _citizen_with_farm(client, "9876500020")
    db = SessionLocal()
    try:
        db.get(Scheme, "pm-kisan").deadline_json = {"date": "2020-01-01", "quote": "The last date to apply is 1 January 2020."}
        db.commit()
        assert _kisan(client, h, pid)["deadline"]["state"] == "closed"
    finally:
        db.get(Scheme, "pm-kisan").deadline_json = None
        db.commit()
        db.close()


def test_changed_scheme_never_shows_a_confident_result_or_verified_badge(client):
    h, pid = _citizen_with_farm(client, "9876500021")
    assert _kisan(client, h, pid)["outcome"] == "likely_qualifies"
    db = SessionLocal()
    try:
        db.get(Scheme, "pm-kisan").status = "needs_update"
        db.commit()
        k = _kisan(client, h, pid)
        assert k["outcome"] == "maybe_confirm_at_office" and k["verified_badge"] is False and k["needs_update"] is True
    finally:
        db.get(Scheme, "pm-kisan").status = "approved"
        db.commit()
        db.close()
