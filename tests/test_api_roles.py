"""Role checks, CSC isolation, protected job endpoint, static pages."""
from tests.conftest import login


def test_role_checks(client):
    citizen = login(client, "9876500005", "citizen")
    assert client.get("/api/admin/stats", headers=citizen).status_code == 403
    assert client.get("/api/admin/stats").status_code == 401
    admin = login(client, "9000000009", "admin")          # listed in ADMIN_PHONES
    assert client.get("/api/admin/stats", headers=admin).json()["schemes"] == 3


def test_staff_roles_cannot_be_self_assigned(client):
    r = client.post("/api/auth/send-otp", json={"phone": "9333333333", "role": "admin"})
    assert r.status_code == 403
    r = client.post("/api/auth/send-otp", json={"phone": "9333333333", "role": "csc_operator"})
    assert r.status_code == 403
    # A registered citizen cannot switch to the admin tab either.
    login(client, "9333333334", "citizen")
    r = client.post("/api/auth/send-otp", json={"phone": "9333333334", "role": "admin"})
    assert r.status_code == 403


def test_admin_approves_csc_operator_who_can_then_log_in(client):
    admin = login(client, "9000000009", "admin")
    g = client.post("/api/admin/roles", json={"phone": "9444444444", "role": "csc_operator"}, headers=admin)
    assert g.status_code == 200
    login(client, "9444444444", "csc_operator")
    staff = client.get("/api/admin/roles", headers=admin).json()["staff"]
    assert any(s["role"] == "csc_operator" for s in staff)
    assert all("9444444444" not in s["phone"] for s in staff)      # masked


def test_csc_operator_sees_only_own_people(client):
    admin = login(client, "9000000009", "admin")
    for ph in ("9111111111", "9222222222"):
        client.post("/api/admin/roles", json={"phone": ph, "role": "csc_operator"}, headers=admin)
    op1, op2 = login(client, "9111111111", "csc_operator"), login(client, "9222222222", "csc_operator")
    pid = client.post("/api/persons", json={"display_name": "Ramu"}, headers=op1).json()["person_id"]
    assert [p["id"] for p in client.get("/api/csc/people", headers=op1).json()["people"]] == [pid]
    assert client.get("/api/csc/people", headers=op2).json()["people"] == []
    assert client.get(f"/api/csc/people/{pid}", headers=op2).status_code == 404
    assert client.get(f"/api/persons/{pid}", headers=op2).status_code == 404
    assert client.get(f"/api/persons/{pid}", headers=op1).status_code == 200


def test_protected_daily_job_endpoint(client):
    assert client.post("/api/jobs/daily-refresh").status_code == 401
    r = client.post("/api/jobs/daily-refresh", headers={"X-Daily-Refresh-Token": "test-token"})
    assert r.status_code == 200


def test_static_pages_served_and_friendly_404(client):
    pages = ["/", "/language.html", "/login.html", "/start.html", "/upload.html", "/questions.html",
             "/results.html", "/schemes.html", "/scheme.html", "/receipt.html", "/track.html",
             "/privacy.html", "/admin.html", "/csc.html", "/faq.html", "/about.html", "/dashboard.html"]
    for page in pages:
        assert client.get(page).status_code == 200, page
    r = client.get("/no-such-page.html")
    assert r.status_code == 404 and "Page not found" in r.text
    assert client.get("/api/nope").json() == {"detail": "Not Found"}
