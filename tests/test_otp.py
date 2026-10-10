"""OTP security: hashing, expiry, lockout, resend cooldown, provider rules, submit code."""
import datetime as dt

import pytest

from app.database import SessionLocal
from app.models import OtpCode, PhoneNumber
from app.otp_providers import OtpDeliveryError, TestOtpProvider, get_otp_provider
from tests.conftest import login


def _send(client, phone, role="citizen"):
    return client.post("/api/auth/send-otp", json={"phone": phone, "role": role})


def _age_otps(phone, minutes=10):
    db = SessionLocal()
    try:
        row = db.query(PhoneNumber).filter(PhoneNumber.phone == phone).first()
        db.query(OtpCode).filter(OtpCode.phone_number_id == row.id).update(
            {"created_at": dt.datetime.utcnow() - dt.timedelta(minutes=minutes)})
        db.commit()
    finally:
        db.close()


def test_code_is_stored_hashed_not_plain(client):
    _send(client, "9700000001")
    db = SessionLocal()
    try:
        row = db.query(PhoneNumber).filter(PhoneNumber.phone == "9700000001").first()
        stored = db.query(OtpCode).filter(OtpCode.phone_number_id == row.id).first().code
    finally:
        db.close()
    assert stored != "123456" and len(stored) == 64


def test_phone_number_validation(client):
    assert _send(client, "12345").status_code == 400
    assert _send(client, "5123456789").status_code == 400      # Indian mobiles start 6-9


def test_resend_cooldown(client):
    assert _send(client, "9700000002").status_code == 200
    r = _send(client, "9700000002")
    assert r.status_code == 429


def test_wrong_code_locks_after_five_attempts(client):
    _send(client, "9700000003")
    for i in range(4):
        r = client.post("/api/auth/verify-otp", json={"phone": "9700000003", "code": "000000", "role": "citizen"})
        assert r.status_code == 400 and "tries left" in r.json()["detail"]
    last = client.post("/api/auth/verify-otp", json={"phone": "9700000003", "code": "000000", "role": "citizen"})
    assert last.status_code == 429
    # Even the right code no longer works: it is burned.
    ok = client.post("/api/auth/verify-otp", json={"phone": "9700000003", "code": "123456", "role": "citizen"})
    assert ok.status_code == 400


def test_code_cannot_be_reused_and_expires(client):
    _send(client, "9700000004")
    body = {"phone": "9700000004", "code": "123456", "role": "citizen"}
    assert client.post("/api/auth/verify-otp", json=body).status_code == 200
    assert client.post("/api/auth/verify-otp", json=body).status_code == 400   # already used

    _age_otps("9700000004")
    _send(client, "9700000004")
    db = SessionLocal()
    try:
        row = db.query(PhoneNumber).filter(PhoneNumber.phone == "9700000004").first()
        db.query(OtpCode).filter(OtpCode.phone_number_id == row.id, OtpCode.consumed.is_(False)).update(
            {"expires_at": dt.datetime.utcnow() - dt.timedelta(seconds=1)})
        db.commit()
    finally:
        db.close()
    assert client.post("/api/auth/verify-otp", json=body).status_code == 400


def test_test_provider_refused_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OTP_PROVIDER", "test")
    with pytest.raises(OtpDeliveryError):
        get_otp_provider()


def test_real_providers_need_credentials(monkeypatch):
    for var in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER", "MSG91_AUTH_KEY", "MSG91_TEMPLATE_ID"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OTP_PROVIDER", "twilio")
    with pytest.raises(OtpDeliveryError):
        get_otp_provider()
    monkeypatch.setenv("OTP_PROVIDER", "msg91")
    with pytest.raises(OtpDeliveryError):
        get_otp_provider()
    monkeypatch.setenv("OTP_PROVIDER", "test")
    monkeypatch.setenv("APP_ENV", "development")
    assert isinstance(get_otp_provider(), TestOtpProvider)


def test_submission_needs_a_fresh_code_sent_to_the_users_own_phone(client):
    h = login(client, "9700000005", "citizen")
    pid = client.post("/api/persons", json={}, headers=h).json()["person_id"]
    client.post("/api/documents/confirm", headers=h, json={"person_id": pid, "verified_fields": {"name": "Asha"}, "user_stated_fields": {}})
    body = {"person_id": pid, "scheme_id": "pm-kisan", "otp_code": "123456"}

    # No code requested yet: refused.
    assert client.post("/api/submissions", json=body, headers=h).status_code == 400
    assert client.post("/api/submissions/request-code", headers=h).status_code == 200
    assert client.post("/api/submissions", json={**body, "otp_code": "999999"}, headers=h).status_code == 400
    ok = client.post("/api/submissions", json=body, headers=h)
    assert ok.status_code == 200
    receipt = ok.json()
    assert receipt["simulated"] is True and receipt["arn"].startswith("SIM-")
    # The same code cannot be replayed.
    assert client.post("/api/submissions", json=body, headers=h).status_code == 400

    t = client.get(f"/api/submissions/track/{receipt['arn']}").json()
    assert t["status"] == "SUBMITTED" and "person_id" not in t
    assert client.get("/api/submissions/track/SIM-NOPE").status_code == 404


def test_cannot_submit_for_someone_elses_record(client):
    h1 = login(client, "9700000006", "citizen")
    pid = client.post("/api/persons", json={}, headers=h1).json()["person_id"]
    h2 = login(client, "9700000007", "citizen")
    client.post("/api/submissions/request-code", headers=h2)
    r = client.post("/api/submissions", json={"person_id": pid, "scheme_id": "pm-kisan", "otp_code": "123456"}, headers=h2)
    assert r.status_code == 404
