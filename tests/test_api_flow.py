"""End-to-end citizen API tests (database set up in conftest.py)."""
from tests.conftest import login


def _person(client, phone):
    h = login(client, phone, "citizen")
    pid = client.post("/api/persons", json={"language": "en"}, headers=h).json()["person_id"]
    return h, pid


def test_health_and_catalogue(client):
    assert client.get("/health").json() == {"status": "ok"}
    d = client.get("/api/schemes").json()
    assert {s["scheme_id"] for s in d["schemes"]} == {"pm-kisan", "pm-ujjwala", "nsap-pension"}
    assert client.get("/api/schemes?q=pension").json()["schemes"][0]["scheme_id"] == "nsap-pension"


def test_i18n_falls_back_to_english_with_preview_flag(client):
    en = client.get("/api/i18n/en").json()
    ta = client.get("/api/i18n/ta").json()
    assert en["preview"] is False and ta["preview"] is True
    assert ta["strings"]["hero_title"] == en["strings"]["hero_title"]
    assert client.get("/api/i18n/hi").json()["strings"]["nav_home"] == "होम"


def test_citizen_flow_numbers_are_coerced_and_results_correct(client):
    h, pid = _person(client, "9876500001")
    no = client.post("/api/persons/consent", json={"person_id": pid, "find_schemes": False}, headers=h)
    assert no.status_code == 400
    yes = client.post("/api/persons/consent", json={"person_id": pid, "find_schemes": True}, headers=h)
    assert yes.status_code == 200

    # Form values arrive as strings; "62" must still satisfy age >= 60.
    for field, value in [("age", "62"), ("gender", "Female"), ("occupation", "Farmer"), ("land_holding", "2")]:
        r = client.post("/api/questions/answer", json={"person_id": pid, "field": field, "value": value}, headers=h)
        assert r.status_code == 200
    bad = client.post("/api/questions/answer", json={"person_id": pid, "field": "age", "value": "abc"}, headers=h)
    assert bad.status_code == 400

    out = {r["scheme_id"]: r for r in client.get(f"/api/results/{pid}", headers=h).json()["results"]}
    assert out["pm-kisan"]["outcome"] == "likely_qualifies"
    assert out["nsap-pension"]["outcome"] == "maybe_confirm_at_office"   # BPL is ambiguous
    assert all("You qualify" not in str(r) for r in out.values())
    # Only the ambiguous BPL condition is left, so the selector stops asking.
    assert client.get(f"/api/questions/next/{pid}", headers=h).json()["done"] is True


def test_selector_asks_closed_question_with_options(client):
    h, pid = _person(client, "9876500006")
    for field, value in [("age", "30"), ("land_holding", "1"), ("gender", "female")]:
        client.post("/api/questions/answer", json={"person_id": pid, "field": field, "value": value}, headers=h)
    q = client.get(f"/api/questions/next/{pid}", headers=h).json()
    assert q["done"] is False and q["question"]["field"] == "occupation"
    assert "farmer" in q["question"]["options"] and q["question"]["question_key"] == "q_occupation"


def test_dob_from_document_derives_age_and_marks_verified(client):
    h, pid = _person(client, "9876500003")
    client.post("/api/documents/confirm", headers=h, json={"person_id": pid,
                "verified_fields": {"date_of_birth": "01-01-1950"}, "user_stated_fields": {"gender": "male"}})
    p = client.get(f"/api/persons/{pid}", headers=h).json()
    assert p["profile"]["age"] >= 76
    assert p["field_sources"]["date_of_birth"] == "verified"
    assert p["field_sources"]["gender"] == "user_stated"


def test_delete_my_data(client):
    h, pid = _person(client, "9876500004")
    assert client.delete(f"/api/persons/{pid}", headers=h).status_code == 200
    assert client.get(f"/api/persons/{pid}", headers=h).status_code == 404


def test_other_people_cannot_read_or_change_my_record(client):
    h1, pid = _person(client, "9876500010")
    h2, _ = _person(client, "9876500011")
    assert client.get(f"/api/persons/{pid}", headers=h2).status_code == 404
    assert client.get(f"/api/results/{pid}", headers=h2).status_code == 404
    assert client.delete(f"/api/persons/{pid}", headers=h2).status_code == 404
    r = client.post("/api/questions/answer", json={"person_id": pid, "field": "age", "value": "40"}, headers=h2)
    assert r.status_code == 404
    assert client.get(f"/api/persons/{pid}").status_code == 401   # anonymous
