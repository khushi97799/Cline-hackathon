"""Shared fixtures: every API test runs on a throwaway SQLite database."""
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["DAILY_REFRESH_TOKEN"] = "test-token"
os.environ["OTP_PROVIDER"] = "test"
os.environ["APP_ENV"] = "development"
os.environ["ADMIN_PHONES"] = "9000000009"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    """Create and seed the throwaway database once, for every test file."""
    seed()


@pytest.fixture(scope="session")
def client(database):
    # Behave like our own pages: they always send this header on writes (CSRF protection).
    with TestClient(app, headers={"X-Requested-With": "SchemeSniper"}) as c:
        yield c


def _expire_cooldown():
    """Tests log in repeatedly; skip the resend cooldown by ageing old OTP rows."""
    import datetime as dt

    from app.database import SessionLocal
    from app.models import OtpCode

    db = SessionLocal()
    try:
        # Age the codes past both the 30-second resend cooldown and the 24-hour daily limit, so tests
        # that log in many times do not trip those (separately tested) protections.
        old = dt.datetime.utcnow() - dt.timedelta(days=2)
        db.query(OtpCode).update({"created_at": old})
        db.commit()
    finally:
        db.close()


def login(client, phone, role):
    _expire_cooldown()
    s = client.post("/api/auth/send-otp", json={"phone": phone, "role": role})
    assert s.status_code == 200, s.text
    r = client.post("/api/auth/verify-otp", json={"phone": phone, "code": "123456", "role": role})
    assert r.status_code == 200, r.text
    client.cookies.clear()      # tests identify users by header; the browser-style cookie would mix them up
    return {"Authorization": "Bearer " + r.json()["access_token"]}
