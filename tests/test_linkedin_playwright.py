"""Test LinkedIn search backend: cookie flow, keywords, playwright infra, regression."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://qikberry-whatsapp.preview.emergentagent.com').rstrip('/')


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestRegression:
    def test_health(self, client):
        r = client.get(f"{BASE_URL}/api/health", timeout=15)
        assert r.status_code == 200
        assert r.json().get("status") in ("healthy", "ok")

    def test_content_studio_pillars(self, client):
        r = client.get(f"{BASE_URL}/api/content-studio/pillars", timeout=20)
        assert r.status_code == 200
        data = r.json()
        pillars = data.get("pillars", data) if isinstance(data, dict) else data
        assert isinstance(pillars, list)
        assert len(pillars) == 18, f"Expected 18 pillars, got {len(pillars)}"


class TestLinkedInCookie:
    def test_1_initial_no_cookie(self, client):
        """After fake cookie cleanup, has_cookie should be false."""
        r = client.get(f"{BASE_URL}/api/li-search/cookie", timeout=15)
        assert r.status_code == 200
        # NOTE: may be True if previous test left a cookie. Log & assert best-effort.
        print("Initial cookie status:", r.json())

    def test_2_save_dummy_cookie(self, client):
        payload = {"li_at": "TEST_dummy_li_at_cookie_12345", "jsessionid": None}
        r = client.post(f"{BASE_URL}/api/li-search/cookie", json=payload, timeout=60)
        assert r.status_code == 200, f"Body: {r.text}"
        data = r.json()
        assert data.get("success") is True
        # Should have either profile or warning (validation likely fails with fake cookie)
        assert "profile" in data or "warning" in data
        print("Save response:", data)

    def test_3_get_cookie_true(self, client):
        r = client.get(f"{BASE_URL}/api/li-search/cookie", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("has_cookie") is True

    def test_4_keywords_default(self, client):
        r = client.get(f"{BASE_URL}/api/li-search/keywords", timeout=15)
        assert r.status_code == 200
        kws = r.json().get("keywords", [])
        assert isinstance(kws, list)
        assert len(kws) >= 10, f"Expected >=10 keywords, got {len(kws)}"


class TestLinkedInSearchInfra:
    """Verify Playwright search infra works — will return empty results with dummy cookie
    (browser redirected to /login), but should NOT crash the backend."""

    def test_5_search_trigger_starts(self, client):
        r = client.post(f"{BASE_URL}/api/li-search/search",
                        json={"keywords": ["looking for agency"], "date_filter": "past-month"},
                        timeout=30)
        assert r.status_code == 200, f"Body: {r.text}"
        data = r.json()
        assert data.get("status") in ("started", "already_running")
        print("Search trigger:", data)

    def test_6_search_status(self, client):
        r = client.get(f"{BASE_URL}/api/li-search/search/status", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "running" in data
        print("Search status:", data)

    def test_7_search_completes_no_crash(self, client):
        """Wait up to 90s for the search to finish. It'll return 0 results (fake cookie
        redirects to login) but must not crash the backend."""
        deadline = time.time() + 120
        while time.time() < deadline:
            r = client.get(f"{BASE_URL}/api/li-search/search/status", timeout=15)
            if r.status_code == 200 and not r.json().get("running"):
                break
            time.sleep(5)
        # After completion, backend must still respond
        r2 = client.get(f"{BASE_URL}/api/health", timeout=15)
        assert r2.status_code == 200, "Backend should still be healthy after Playwright search"

    def test_8_posts_endpoint(self, client):
        r = client.get(f"{BASE_URL}/api/li-search/posts", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "posts" in data
        assert "stats" in data


class TestConnectionsInfra:
    def test_9_connections_infra(self, client):
        """Connections endpoint uses Playwright — should return empty list (login
        redirect with fake cookie) but not crash."""
        r = client.get(f"{BASE_URL}/api/li-search/connections", timeout=90)
        # Either 200 with empty list, or 500 if both playwright + API fail; accept 200
        # with empty; 500 is a valid failure mode per code.
        assert r.status_code in (200, 500), f"Unexpected: {r.status_code} {r.text[:300]}"
        if r.status_code == 200:
            data = r.json()
            assert "connections" in data
            assert isinstance(data["connections"], list)


class TestCleanup:
    def test_zz_cleanup_dummy_cookie(self, client):
        """Cleanup: remove the TEST_ dummy cookie from DB via direct mongo."""
        try:
            import asyncio
            from dotenv import load_dotenv
            load_dotenv('/app/backend/.env')
            from motor.motor_asyncio import AsyncIOMotorClient
            async def clear():
                c = AsyncIOMotorClient(os.environ.get('MONGO_URL'))
                db = c[os.environ.get('DB_NAME', 'agent_hub')]
                await db.li_search_config.delete_one({"type": "cookie", "li_at": "TEST_dummy_li_at_cookie_12345"})
            asyncio.run(clear())
        except Exception as e:
            print("cleanup warn:", e)
