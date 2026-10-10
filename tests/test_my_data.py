"""A person can see, change and correct everything stored about them."""
from app.database import SessionLocal
from app.models import Consent
from tests.conftest import login


def setup_person(client, phone, **fields):
    h = login(client, phone, "citizen")
    pid = client.post("/api/persons", json={"display_name": "Asha Devi"}, headers=h).json()["person_id"]
    client.post("/api/documents/confirm", headers=h, json={"person_id": pid, "verified_fields": {"date_of_birth": "01-01-1950", "gender": "female"},
                                                           "user_stated_fields": {"occupation": "farmer", **fields}})
    return h, pid


def test_i_can_see_exactly_what_is_stored(client):
    h, pid = setup_person(client, "9400000001")
    me = client.get("/api/me/people", headers=h).json()
    assert me["role"] == "citizen" and [p["id"] for p in me["people"]] == [pid]
    p = me["people"][0]
    assert p["display_name"] == "Asha Devi" and p["profile"]["gender"] == "female"
    assert p["field_sources"]["gender"] == "verified" and p["field_sources"]["occupation"] == "user_stated"
    assert "9400000001" not in str(me)                                              # the phone number is not part of the profile


def test_i_can_edit_a_value_and_it_becomes_user_stated(client):
    h, pid = setup_person(client, "9400000002")
    p = client.put(f"/api/me/people/{pid}/fields/gender", json={"value": "Male"}, headers=h).json()
    assert p["profile"]["gender"] == "male" and p["field_sources"]["gender"] == "user_stated"   # no longer from a document
    assert client.put(f"/api/me/people/{pid}/fields/age", json={"value": "abc"}, headers=h).status_code == 400
    assert client.put(f"/api/me/people/{pid}/fields/aadhaar_number", json={"value": "1"}, headers=h).status_code == 404


def test_edits_cannot_smuggle_in_confidential_numbers(client):
    h, pid = setup_person(client, "9400000003")
    for bad in ("1234 5678 9012", "ABCDE1234F", "9876543210", "me@example.com"):
        r = client.put(f"/api/me/people/{pid}/fields/occupation", json={"value": bad}, headers=h)
        assert r.status_code == 400, bad
        assert bad not in r.text                                                    # the error never echoes it back
    assert client.put(f"/api/me/people/{pid}/name", json={"name": "123456789012"}, headers=h).status_code == 400
    assert client.get(f"/api/me/people/{pid}", headers=h).json()["profile"]["occupation"] == "farmer"


def test_i_can_remove_one_value(client):
    h, pid = setup_person(client, "9400000004")
    p = client.delete(f"/api/me/people/{pid}/fields/occupation", headers=h).json()
    assert "occupation" not in p["profile"] and "occupation" not in p["field_sources"]
    p = client.delete(f"/api/me/people/{pid}/fields/date_of_birth", headers=h).json()
    assert "date_of_birth" not in p["profile"] and "age" not in p["profile"]          # the age derived from it goes too
    assert client.delete(f"/api/me/people/{pid}/fields/not_a_field", headers=h).status_code == 404


def test_i_can_rename_and_change_my_consents(client):
    h, pid = setup_person(client, "9400000005")
    assert client.put(f"/api/me/people/{pid}/name", json={"name": "Asha Kumari"}, headers=h).json()["display_name"] == "Asha Kumari"
    r = client.put(f"/api/me/people/{pid}/consent", json={"save_profile": True, "notifications": True}, headers=h).json()
    assert r["consent"] == {"save_profile": True, "notifications": True} and r["saved"] is True
    r = client.put(f"/api/me/people/{pid}/consent", json={"save_profile": False, "notifications": False}, headers=h).json()
    assert r["consent"] == {"save_profile": False, "notifications": False} and r["saved"] is False
    db = SessionLocal()
    try:
        assert db.query(Consent).filter(Consent.person_id == pid).count() >= 2        # every change is on record
    finally:
        db.close()


def test_export_contains_my_data_but_no_full_phone_number(client):
    h, pid = setup_person(client, "9400000008")
    r = client.get("/api/me/export", headers=h)
    assert "attachment" in r.headers["content-disposition"]
    d = r.json()
    assert d["people"][0]["profile"]["gender"] == "female" and "9400000008" not in str(d)
    assert d["phone_hint"].startswith("94") and "*" in d["phone_hint"]
