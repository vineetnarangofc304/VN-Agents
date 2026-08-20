"""Tests for Voyager posting endpoint, cookie status, company pages generate (iteration 25)."""
import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- health ----------
class TestHealth:
    def test_health(self, client):
        r = client.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("status") in ("healthy", "ok")


# ---------- li-search cookie ----------
class TestCookieStatus:
    def test_cookie_status(self, client):
        r = client.get(f"{BASE_URL}/api/li-search/cookie", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)
        assert "_id" not in str(data), f"Mongo _id leaked: {data}"
        # must expose some flag about configuration
        assert any(k in data for k in ("configured", "has_cookie", "li_at", "status")), data
        print("cookie status:", data)


# ---------- voyager-post ----------
class TestVoyagerPost:
    def test_empty_content_returns_400(self, client):
        r = client.post(f"{BASE_URL}/api/li-search/voyager-post", json={"content": ""}, timeout=60)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:300]}"
        assert "content" in r.json().get("detail", "").lower()

    def test_missing_content_key_returns_400(self, client):
        r = client.post(f"{BASE_URL}/api/li-search/voyager-post", json={}, timeout=60)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:300]}"

    def test_endpoint_exists_and_no_500(self, client):
        """With content present, endpoint must not crash (500). Expired cookie -> 4xx/502."""
        r = client.post(
            f"{BASE_URL}/api/li-search/voyager-post",
            json={"content": "TEST_ do not publish - automated test probe"},
            timeout=120,
        )
        print("voyager-post status:", r.status_code, r.text[:300])
        assert r.status_code != 404, "endpoint missing"
        assert r.status_code != 500, f"unhandled server error: {r.text[:300]}"
        if r.status_code in (200, 201):
            body = r.json()
            assert body.get("success") is True
            pytest.fail("A real LinkedIn post was published by the test probe - endpoint accepted the post")
        else:
            assert 400 <= r.status_code < 600
            assert "detail" in r.json()

    def test_bad_image_path_ignored_not_crash(self, client):
        r = client.post(
            f"{BASE_URL}/api/li-search/voyager-post",
            json={"content": "TEST_ probe with bad image", "image_path": "/tmp/does_not_exist_xyz.png"},
            timeout=120,
        )
        print("bad image path status:", r.status_code, r.text[:200])
        assert r.status_code != 500, r.text[:300]


# ---------- company pages ----------
class TestCompanyPages:
    def test_list_pages(self, client):
        r = client.get(f"{BASE_URL}/api/company-pages", timeout=30)
        assert r.status_code == 200, r.text
        pages = r.json()
        if isinstance(pages, dict):
            pages = pages.get("pages", pages.get("items", []))
        assert isinstance(pages, list)
        assert len(pages) == 5, f"expected 5 company pages, got {len(pages)}"
        for p in pages:
            assert "org_id" in p and "name" in p
            assert "_id" not in p
        assert any(p["org_id"] == "69021406" for p in pages), [p["org_id"] for p in pages]

    def test_generate_content_no_image(self, client):
        r = client.post(
            f"{BASE_URL}/api/company-pages/69021406/generate",
            json={"generate_image": False},
            timeout=180,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        data = r.json()
        assert isinstance(data.get("content"), str) and len(data["content"]) > 100, data
        assert data.get("image_path") in (None, ""), data.get("image_path")
        assert data.get("company")
        print("generated content len:", len(data["content"]))

    def test_generate_unknown_org_404(self, client):
        r = client.post(
            f"{BASE_URL}/api/company-pages/000000/generate",
            json={"generate_image": False},
            timeout=60,
        )
        assert r.status_code == 404, f"{r.status_code}: {r.text[:200]}"
