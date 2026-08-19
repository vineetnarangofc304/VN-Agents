"""Tests for Company Pages CRUD + AI generation endpoints."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://qikberry-whatsapp.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api/company-pages"

EXPECTED_ORGS = {"69021406", "143338927", "142891970", "105361431", "125583973"}
TEMP_ORG_ID = "TEST_99999999"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ============== LIST ==============
def test_list_company_pages(sess):
    r = sess.get(API, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "pages" in data
    ids = {p["org_id"] for p in data["pages"]}
    missing = EXPECTED_ORGS - ids
    assert not missing, f"Missing expected org_ids: {missing}. Got: {ids}"

    for p in data["pages"]:
        if p["org_id"] in EXPECTED_ORGS:
            assert p.get("name"), f"Page {p['org_id']} has no name"
            assert "pillars" in p
            assert "total_posts" in p
            assert "posts_today" in p
            assert "posts_per_day" in p


# ============== CREATE / UPDATE / DELETE ==============
def test_create_temp_page(sess):
    # ensure clean
    sess.delete(f"{API}/{TEMP_ORG_ID}", timeout=10)

    r = sess.post(API, json={
        "org_id": TEMP_ORG_ID,
        "name": "TEST_Temp Page",
        "description": "Test description",
        "pillars": ["ai", "automation"],
        "posts_per_day": 3,
        "schedule_enabled": False,
    }, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True

    # verify via list
    r2 = sess.get(API, timeout=15)
    page = next((p for p in r2.json()["pages"] if p["org_id"] == TEMP_ORG_ID), None)
    assert page is not None
    assert page["name"] == "TEST_Temp Page"
    assert page["pillars"] == ["ai", "automation"]
    assert page["posts_per_day"] == 3


def test_update_temp_page(sess):
    r = sess.put(f"{API}/{TEMP_ORG_ID}", json={
        "schedule_enabled": True,
        "pillars": ["ai", "automation", "growth"],
    }, timeout=15)
    assert r.status_code == 200, r.text

    r2 = sess.get(API, timeout=15)
    page = next((p for p in r2.json()["pages"] if p["org_id"] == TEMP_ORG_ID), None)
    assert page is not None
    assert page["schedule_enabled"] is True
    assert page["pillars"] == ["ai", "automation", "growth"]


def test_update_nonexistent_returns_404(sess):
    r = sess.put(f"{API}/NONEXISTENT_ID_XYZ", json={"schedule_enabled": True}, timeout=10)
    assert r.status_code == 404


def test_delete_temp_page(sess):
    r = sess.delete(f"{API}/{TEMP_ORG_ID}", timeout=10)
    assert r.status_code == 200
    # verify removed
    r2 = sess.get(API, timeout=15)
    ids = {p["org_id"] for p in r2.json()["pages"]}
    assert TEMP_ORG_ID not in ids


def test_delete_nonexistent_returns_404(sess):
    r = sess.delete(f"{API}/NONEXISTENT_ID_XYZ", timeout=10)
    assert r.status_code == 404


# ============== POST HISTORY ==============
def test_get_post_history(sess):
    org_id = "69021406"
    r = sess.get(f"{API}/{org_id}/posts", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "posts" in data
    assert isinstance(data["posts"], list)


# ============== AI GENERATE ==============
def test_generate_content_fundle(sess):
    org_id = "69021406"
    r = sess.post(f"{API}/{org_id}/generate", json={
        "pillar": "AI automation",
        "generate_image": False,  # skip image to keep test fast
    }, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("content"), "No content generated"
    assert isinstance(data["content"], str)
    assert len(data["content"]) > 50, f"Content too short: {data['content']}"
    assert data.get("company")


def test_generate_content_nonexistent_page(sess):
    r = sess.post(f"{API}/NONEXISTENT_XYZ/generate", json={"generate_image": False}, timeout=15)
    assert r.status_code == 404
    # Must be proper JSON error, not an HTML/Cloudflare error page
    assert "application/json" in r.headers.get("content-type", "")
    assert r.json().get("detail") == "Company page not found"


def test_generate_never_returns_5xx_gateway_error(sess):
    """Regression for the 520 Cloudflare bug: response must be a valid JSON
    HTTP response (200 on success, 502/503 on AI failure) - never 520/no-response."""
    org_id = "69021406"
    r = sess.post(f"{API}/{org_id}/generate", json={
        "pillar": "Retail AI",
        "generate_image": False,
    }, timeout=90)
    assert r.status_code in (200, 502, 503), f"Unexpected status {r.status_code}: {r.text[:300]}"
    assert "application/json" in r.headers.get("content-type", ""), r.text[:300]
    body = r.json()
    if r.status_code == 200:
        assert body.get("content")
        assert body.get("pillar") == "Retail AI"
        assert body.get("image_path") is None
    else:
        assert body.get("detail")


# ============== POSTING (520 regression) ==============
POST_OK_STATUSES = (200, 400, 401, 403, 502)


def test_post_to_company_page_graceful_failure(sess):
    """Regression for the 520 Cloudflare bug on Post Now: the endpoint must
    always return a proper JSON HTTP response, never crash the worker."""
    org_id = "69021406"
    r = sess.post(f"{API}/{org_id}/post", json={
        "content": "TEST_ regression post - please ignore.",
    }, timeout=90)
    assert r.status_code in POST_OK_STATUSES, f"Unexpected status {r.status_code}: {r.text[:400]}"
    assert "application/json" in r.headers.get("content-type", ""), r.text[:300]
    body = r.json()
    if r.status_code == 200:
        assert body.get("success") is True
        assert "post_id" in body
    else:
        assert body.get("detail"), r.text[:300]
        assert "<html" not in r.text.lower()


def test_post_to_nonexistent_page_returns_404(sess):
    r = sess.post(f"{API}/NONEXISTENT_XYZ/post", json={"content": "TEST_ should 404"}, timeout=20)
    assert r.status_code == 404, r.text[:300]
    assert "application/json" in r.headers.get("content-type", "")
    assert r.json().get("detail") == "Company page not found"


def test_post_missing_content_returns_422(sess):
    r = sess.post(f"{API}/69021406/post", json={}, timeout=20)
    assert r.status_code == 422, r.text[:300]


def test_failed_post_is_recorded_in_history(sess):
    """A failed LinkedIn post must be logged with status=failed (not lost)."""
    org_id = "69021406"
    marker = f"TEST_history_marker_{int(time.time())}"
    r = sess.post(f"{API}/{org_id}/post", json={"content": marker}, timeout=90)
    assert r.status_code in POST_OK_STATUSES, r.text[:300]

    h = sess.get(f"{API}/{org_id}/posts?limit=20", timeout=20)
    assert h.status_code == 200
    posts = h.json()["posts"]
    match = next((p for p in posts if p.get("content") == marker), None)
    if r.status_code == 200:
        assert match is not None and match.get("status") == "published"
    else:
        # 400/401/403/502 paths all persist a failed attempt
        if r.status_code in (400, 401, 403, 502) and "No LinkedIn account connected" not in r.json().get("detail", "") \
                and "LinkedIn token expired. Go to" not in r.json().get("detail", ""):
            assert match is not None, "Failed post attempt was not recorded in history"
            assert match.get("status") == "failed"
            assert match.get("error")


# ============== org_id SANITIZATION ==============
def test_create_page_strips_trailing_slash(sess):
    dirty = f"  {TEMP_ORG_ID}/  "
    sess.delete(f"{API}/{TEMP_ORG_ID}", timeout=10)
    r = sess.post(API, json={
        "org_id": dirty,
        "name": "TEST_Sanitize Page",
        "pillars": ["x"],
    }, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("org_id") == TEMP_ORG_ID, r.text

    r2 = sess.get(API, timeout=15)
    ids = {p["org_id"] for p in r2.json()["pages"]}
    assert TEMP_ORG_ID in ids
    assert f"{TEMP_ORG_ID}/" not in ids

    # cleanup
    d = sess.delete(f"{API}/{TEMP_ORG_ID}", timeout=10)
    assert d.status_code == 200
