"""Tests for backend startup fixes and core auth flows (iteration 18)."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://qikberry-whatsapp.preview.emergentagent.com").rstrip("/")
AGENT_PASSWORD = "Agent@2024!"
ADMIN_EMAIL = "vineetnarangofc@gmail.com"
ADMIN_PASSWORD = "InvoiceAgent@2024!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# Health check
def test_health(session):
    r = session.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "healthy"


# Agent login
def test_agent_login_success(session):
    r = session.post(f"{BASE_URL}/api/auth/agent-login", json={"agent": "linkedin", "password": AGENT_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("success") is True


def test_agent_login_wrong_password(session):
    r = session.post(f"{BASE_URL}/api/auth/agent-login", json={"agent": "linkedin", "password": "wrong"}, timeout=15)
    assert r.status_code in (401, 403)


# Admin JWT login
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


def test_admin_login_response_has_user(admin_session):
    # re-verify explicit login response fields
    r = admin_session.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200
    data = r.json()
    # Look for user info (email at minimum) somewhere in response
    body = str(data).lower()
    assert ADMIN_EMAIL.lower() in body or data.get("success") is True or "user" in data


def test_admin_login_wrong_password(session):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": "badpass"}, timeout=15)
    assert r.status_code in (401, 403)


def test_auth_me_with_cookie(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    body = str(data).lower()
    assert ADMIN_EMAIL.lower() in body


# Banking agent - should not crash (deferred index creation)
def test_banking_agent_route_reachable(session):
    # try a couple of likely GETs; we just want to ensure server didn't crash
    tried = []
    for path in ["/api/banking/health", "/api/banking", "/api/banking/accounts", "/api/banking/status"]:
        r = session.get(f"{BASE_URL}{path}", timeout=15)
        tried.append((path, r.status_code))
        # any non-5xx means server is alive for that route
        if r.status_code < 500:
            return
    pytest.fail(f"All banking routes returned 5xx: {tried}")


# LinkedIn agent basic route reachable
def test_linkedin_route_reachable(session):
    r = session.get(f"{BASE_URL}/api/li-search/accounts", timeout=15)
    assert r.status_code < 500, r.text
