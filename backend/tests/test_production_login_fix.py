"""Tests for iteration 23: production login fix + core endpoints (health, agent-login, company-pages)."""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

AGENT_PASSWORD = "Agent@2024!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- Health ---
class TestHealth:
    def test_health(self, client):
        r = client.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["status"] == "healthy"
        assert isinstance(data.get("service"), str)

    def test_root(self, client):
        r = client.get(f"{BASE_URL}/api/", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("status") == "running"


# --- Agent login ---
class TestAgentLogin:
    def test_login_success(self, client):
        r = client.post(f"{BASE_URL}/api/auth/agent-login",
                        json={"agent": "linkedin", "password": AGENT_PASSWORD}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["success"] is True
        assert data["agent"] == "linkedin"

    def test_login_wrong_password(self, client):
        r = client.post(f"{BASE_URL}/api/auth/agent-login",
                        json={"agent": "linkedin", "password": "wrong"}, timeout=30)
        assert r.status_code == 401, r.text[:300]

    def test_login_missing_field(self, client):
        r = client.post(f"{BASE_URL}/api/auth/agent-login", json={"password": AGENT_PASSWORD}, timeout=30)
        assert r.status_code == 422, r.text[:300]

    def test_login_latency_under_10s(self, client):
        r = client.post(f"{BASE_URL}/api/auth/agent-login",
                        json={"agent": "linkedin", "password": AGENT_PASSWORD}, timeout=30)
        assert r.status_code == 200
        assert r.elapsed.total_seconds() < 10, f"login took {r.elapsed.total_seconds()}s"


# --- Company pages ---
class TestCompanyPages:
    def test_list_company_pages(self, client):
        r = client.get(f"{BASE_URL}/api/company-pages", timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        pages = data.get("pages") if isinstance(data, dict) else data
        assert isinstance(pages, list)
        assert len(pages) == 5, f"expected 5 pages, got {len(pages)}"
        for p in pages:
            assert p.get("org_id")
            assert p.get("name")
            assert "_id" not in p, "MongoDB _id leaked in response"

    def test_page_posts(self, client):
        r = client.get(f"{BASE_URL}/api/company-pages", timeout=60)
        payload = r.json()
        pages = payload.get("pages") if isinstance(payload, dict) else payload
        org_id = pages[0]["org_id"]
        d = client.get(f"{BASE_URL}/api/company-pages/{org_id}/posts", timeout=60)
        assert d.status_code == 200, d.text[:300]
        posts = d.json().get("posts")
        assert isinstance(posts, list)
        for p in posts:
            assert "_id" not in p, "MongoDB _id leaked in posts response"
