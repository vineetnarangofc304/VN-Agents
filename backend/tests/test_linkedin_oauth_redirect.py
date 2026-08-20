"""Iteration 24: LinkedIn OAuth redirect-URI fix + core endpoint regression."""
import os
from urllib.parse import urlparse, parse_qs

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

backend_env = dotenv_values("/app/backend/.env")
PROD_DOMAIN = backend_env.get("PROD_DOMAIN", "https://vnagents.agenticindia.ai")
AGENT_PASSWORD = backend_env.get("AGENT_PASSWORD", "Agent@2024!")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Health ----------
class TestHealth:
    def test_health(self, client):
        r = client.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("status") in ("healthy", "ok"), data


# ---------- LinkedIn OAuth ----------
class TestLinkedInOAuth:
    @pytest.fixture(scope="class")
    def auth_payload(self, client):
        r = client.get(f"{BASE_URL}/api/linkedin/auth", timeout=30)
        assert r.status_code == 200, r.text[:300]
        return r.json()

    def test_auth_returns_url_and_state(self, auth_payload):
        assert "auth_url" in auth_payload and "state" in auth_payload
        assert auth_payload["auth_url"].startswith(
            "https://www.linkedin.com/oauth/v2/authorization?"
        )
        assert isinstance(auth_payload["state"], str) and len(auth_payload["state"]) > 20

    def test_redirect_uri_is_production_domain(self, auth_payload):
        qs = parse_qs(urlparse(auth_payload["auth_url"]).query)
        redirect_uri = qs["redirect_uri"][0]
        expected = f"{PROD_DOMAIN}/api/linkedin/callback"
        assert redirect_uri == expected, f"got {redirect_uri}"
        assert "preview" not in redirect_uri

    def test_scope_includes_org_social(self, auth_payload):
        qs = parse_qs(urlparse(auth_payload["auth_url"]).query)
        scope = qs["scope"][0]
        for s in ["openid", "profile", "w_member_social", "w_organization_social"]:
            assert s in scope, f"missing scope {s} in {scope}"

    def test_client_id_present(self, auth_payload):
        qs = parse_qs(urlparse(auth_payload["auth_url"]).query)
        assert qs["response_type"][0] == "code"
        assert len(qs["client_id"][0]) > 5

    def test_callback_without_code_returns_400(self, client):
        r = client.get(f"{BASE_URL}/api/linkedin/callback", timeout=30)
        assert r.status_code == 400, f"{r.status_code} {r.text[:300]}"
        assert "Missing code or state" in r.text

    def test_callback_with_error_param_returns_html(self, client):
        r = client.get(
            f"{BASE_URL}/api/linkedin/callback",
            params={"error": "user_cancelled_login", "error_description": "User cancelled"},
            timeout=30,
        )
        assert r.status_code == 200
        assert "LinkedIn Connection Failed" in r.text

    def test_callback_with_bogus_code_no_crash(self, client):
        r = client.get(
            f"{BASE_URL}/api/linkedin/callback",
            params={"code": "TEST_bogus_code", "state": "TEST_bogus_state"},
            timeout=60,
        )
        assert r.status_code in (400, 200), f"{r.status_code} {r.text[:300]}"
        assert r.status_code != 500

    def test_accounts_no_objectid_or_token_leak(self, client):
        r = client.get(f"{BASE_URL}/api/linkedin/accounts", timeout=30)
        assert r.status_code == 200
        accounts = r.json()["accounts"]
        assert isinstance(accounts, list)
        for a in accounts:
            assert "_id" not in a
            assert "access_token" not in a


# ---------- Agent login ----------
class TestAgentLogin:
    def test_agent_login_success(self, client):
        r = client.post(
            f"{BASE_URL}/api/auth/agent-login",
            json={"agent": "linkedin", "password": AGENT_PASSWORD},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("success") is True, data
        assert data.get("agent") == "linkedin", data

    def test_agent_login_wrong_password(self, client):
        r = client.post(
            f"{BASE_URL}/api/auth/agent-login",
            json={"agent": "linkedin", "password": "TEST_wrong"},
            timeout=30,
        )
        assert r.status_code == 401, r.text[:300]


# ---------- Company pages ----------
class TestCompanyPages:
    def test_company_pages_list(self, client):
        r = client.get(f"{BASE_URL}/api/company-pages", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        pages = data if isinstance(data, list) else data.get("pages", [])
        assert isinstance(pages, list)
        assert len(pages) > 0, "no configured company pages"
        for p in pages:
            assert "_id" not in p
            assert p.get("org_id") or p.get("organization_id") or p.get("name")
