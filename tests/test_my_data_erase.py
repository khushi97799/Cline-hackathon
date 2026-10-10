"""Deleting my data really deletes it, and nobody else can touch it."""
from app.database import SessionLocal
from app.models import AuditLog, Consent, OtpCode, Person, PhoneNumber, Submission
from tests.conftest import login
from tests.test_my_data import setup_person


def test_other_people_cannot_touch_my_data(client):
    h1, pid = setup_person(client, "9400000006")
    h2 = login(client, "9400000007", "citizen")
    for call in (lambda: client.get(f"/api/me/people/{pid}", headers=h2),
                 lambda: client.put(f"/api/me/people/{pid}/fields/gender", json={"value": "male"}, headers=h2),
                 lambda: client.delete(f"/api/me/people/{pid}/fields/gender", headers=h2),
                 lambda: client.put(f"/api/me/people/{pid}/name", json={"name": "X"}, headers=h2),
                 lambda: client.put(f"/api/me/people/{pid}/consent", json={"save_profile": True}, headers=h2),
                 lambda: client.delete(f"/api/me/people/{pid}", headers=h2)):
        assert call().status_code == 404
    assert client.get("/api/me/people", headers=h2).json()["people"] == []
    assert client.get("/api/me/people").status_code == 401


def test_delete_one_person_removes_their_records(client):
    h, pid = setup_person(client, "9400000009")
    assert client.delete(f"/api/me/people/{pid}", headers=h).status_code == 200
    db = SessionLocal()
    try:
        assert db.get(Person, pid) is None
        assert db.query(Consent).filter(Consent.person_id == pid).count() == 0
        assert db.query(Submission).filter(Submission.person_id == pid).count() == 0
    finally:
        db.close()


def test_delete_account_erases_the_phone_number_and_login_codes(client):
    h, pid = setup_person(client, "9400000010")
    db = SessionLocal()
    try:
        phone_id = db.query(PhoneNumber).filter(PhoneNumber.phone == "9400000010").one().id
    finally:
        db.close()
    assert client.delete("/api/me/account", headers=h).status_code == 200
    db = SessionLocal()
    try:
        assert db.query(PhoneNumber).filter(PhoneNumber.phone == "9400000010").count() == 0
        assert db.query(OtpCode).filter(OtpCode.phone_number_id == phone_id).count() == 0
        assert db.get(Person, pid) is None
        entry = db.query(AuditLog).filter(AuditLog.action == "delete_account").first()
        assert entry is not None and entry.actor_id is None and "9400000010" not in f"{entry.target} {entry.details}"
    finally:
        db.close()
    assert client.get("/api/me/people", headers=h).status_code == 401              # the old login no longer works
    login(client, "9400000010", "citizen")                                          # and the person can start fresh


def test_staff_cannot_erase_themselves_through_the_citizen_route(client):
    admin = login(client, "9000000009", "admin")
    assert client.delete("/api/me/account", headers=admin).status_code == 403


def test_csc_operator_manages_only_the_people_they_created(client):
    admin = login(client, "9000000009", "admin")
    for ph in ("9300000001", "9300000002"):
        client.post("/api/admin/roles", json={"phone": ph, "role": "csc_operator"}, headers=admin)
    op1, op2 = login(client, "9300000001", "csc_operator"), login(client, "9300000002", "csc_operator")
    pid = client.post("/api/persons", json={"display_name": "Ramu"}, headers=op1).json()["person_id"]
    assert [p["display_name"] for p in client.get("/api/me/people", headers=op1).json()["people"]] == ["Ramu"]
    assert client.get("/api/me/people", headers=op2).json()["people"] == []
    assert client.delete(f"/api/me/people/{pid}", headers=op2).status_code == 404
    assert client.delete(f"/api/me/people/{pid}", headers=op1).status_code == 200


def test_no_personal_data_in_the_audit_log(client):
    db = SessionLocal()
    try:
        for e in db.query(AuditLog).all():
            blob = f"{e.action} {e.target} {e.details}"
            assert not any(n in blob for n in ("9400000", "9876500", "Asha", "Ramu")), blob
    finally:
        db.close()
