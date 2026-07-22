import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://automation-platform-10.preview.emergentagent.com').rstrip('/')


@pytest.fixture
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestLinkedInCookie:
    def test_post_cookie_with_only_li_at_returns_success(self, api):
        """POST /api/li-search/cookie with only li_at (no JSESSIONID) should
        NOT return an error — must save cookie and return success (possibly warning)."""
        payload = {"li_at": "AQEDAQxxxxxxxxfake_cookie_for_testing"}
        resp = api.post(f"{BASE_URL}/api/li-search/cookie", json=payload, timeout=30)
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data.get("success") is True, f"Expected success:true, got {data}"
        # profile field must exist
        assert "profile" in data
        # For a fake cookie, we expect a warning (partial validation)
        # (not asserted strict, but at least field could exist)

    def test_get_cookie_returns_has_cookie_true_after_save(self, api):
        # ensure a cookie is saved
        api.post(f"{BASE_URL}/api/li-search/cookie",
                 json={"li_at": "AQEDAQxxxxxxxxfake_cookie_for_testing"}, timeout=30)
        resp = api.get(f"{BASE_URL}/api/li-search/cookie", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("has_cookie") is True

    def test_post_cookie_with_both_returns_success(self, api):
        payload = {"li_at": "AQEDAQxxxxxxxxfake_cookie_for_testing",
                   "jsessionid": "ajax:1234567890"}
        resp = api.post(f"{BASE_URL}/api/li-search/cookie", json=payload, timeout=30)
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    def test_search_endpoint_accepts_request_with_saved_cookie(self, api):
        """After saving cookie, search endpoint should NOT return 400 no-cookie error."""
        api.post(f"{BASE_URL}/api/li-search/cookie",
                 json={"li_at": "AQEDAQxxxxxxxxfake_cookie_for_testing"}, timeout=30)
        resp = api.post(f"{BASE_URL}/api/li-search/search", json={"keywords": ["test"]}, timeout=15)
        # Should be 200 with started/already_running (not 400)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("status") in ("started", "already_running")
