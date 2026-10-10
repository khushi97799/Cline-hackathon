"""Confidential identifiers must never reach the database, and the browser must not hold the token."""
import pathlib
import re

import pytest

from app.pii import PiiError, clean_profile_value, find_identifier
from tests.conftest import login

STATIC = pathlib.Path(__file__).resolve().parent.parent / "static"


@pytest.mark.parametrize("value", [
    "1234 5678 9012", "123456789012", "1234-5678-9012", "ABCDE1234F", "abc1234567", "M1234567", "SBIN0001234",
    "9876543210", "+91 98765 43210", "123456789012345", "me@example.com", "ramu@okaxis",
    "My Aadhaar is 2345 6789 0123 ok",
])
def test_identifier_shaped_values_are_refused(value):
    with pytest.raises(PiiError) as e:
        clean_profile_value("name", value)
    assert value not in str(e.value)               # the error never repeats the secret


@pytest.mark.parametrize("value", ["Asha Devi", "Ram Kumar Yadav", "62", "farmer", "Uttar Pradesh", "01-01-1950", "2.5", "Rs 40,000"])
def test_normal_values_pass(value):
    assert clean_profile_value("name", value) == value


def test_only_profile_fields_can_be_stored():
    for field in ("aadhaar_number", "password", "otp", "token", "pan", "bank_account", "phone"):
        with pytest.raises(PiiError):
            clean_profile_value(field, "x")


def test_value_limits_and_control_characters():
    with pytest.raises(PiiError):
        clean_profile_value("name", "a" * 500)
    assert clean_profile_value("name", "Asha\x00 Devi\x07") == "Asha Devi"
    assert find_identifier("farmer") is None


def test_api_refuses_identifiers_and_unknown_fields(client):
    h = login(client, "9500000001", "citizen")
    pid = client.post("/api/persons", json={}, headers=h).json()["person_id"]
    r = client.post("/api/questions/answer", json={"person_id": pid, "field": "occupation", "value": "123456789012"}, headers=h)
    assert r.status_code == 400 and "Aadhaar" in r.json()["detail"]
    r = client.post("/api/questions/answer", json={"person_id": pid, "field": "aadhaar_number", "value": "x"}, headers=h)
    assert r.status_code == 400
    r = client.post("/api/documents/confirm", headers=h, json={"person_id": pid, "verified_fields": {"name": "ABCDE1234F"}, "user_stated_fields": {}})
    assert r.status_code == 400
    assert client.get(f"/api/persons/{pid}", headers=h).json()["profile"] == {}      # nothing was stored


def test_login_token_is_an_httponly_cookie_and_logout_clears_it(client):
    client.post("/api/auth/send-otp", json={"phone": "9500000002", "role": "citizen"})
    r = client.post("/api/auth/verify-otp", json={"phone": "9500000002", "code": "123456", "role": "citizen"})
    cookie = r.headers["set-cookie"]
    assert "ss_session=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert client.get("/api/auth/me").json()["role"] == "citizen"          # the cookie alone authenticates
    me = client.get("/api/auth/me").json()
    assert "9500000002" not in str(me)                                       # phone is masked
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()


def test_cookie_requests_need_the_csrf_header(client):
    client.post("/api/auth/send-otp", json={"phone": "9500000003", "role": "citizen"})
    client.post("/api/auth/verify-otp", json={"phone": "9500000003", "code": "123456", "role": "citizen"})
    r = client.post("/api/persons", json={}, headers={"X-Requested-With": ""})
    assert r.status_code == 403 and "security header" in r.json()["detail"]
    assert client.post("/api/persons", json={}).status_code == 200
    client.cookies.clear()


def test_security_headers_and_no_store_on_personal_data(client):
    r = client.get("/")
    assert "script-src 'self'" in r.headers["content-security-policy"] and r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    h = login(client, "9500000004", "citizen")
    assert client.get("/api/auth/me", headers=h).headers["cache-control"] == "no-store"


def test_no_page_uses_inline_scripts_or_stores_the_token_in_the_browser():
    for page in STATIC.glob("*.html"):
        html = page.read_text(encoding="utf-8-sig")
        assert not re.search(r"<script>(?!\s*</script>)", html), f"{page.name} has an inline script (blocked by CSP)"
        assert not re.search(r"\son(click|change|input|load|error)=", html), f"{page.name} has an inline handler"
        assert "javascript:" not in html, page.name
    for js in STATIC.rglob("*.js"):
        src = js.read_text(encoding="utf-8-sig")
        assert "ss_token" not in src and "access_token" not in src or js.name == "login.js", js.name
        assert "innerHTML" not in src or "esc(" in src or js.name in {"header.js", "voice.js"}, js.name
