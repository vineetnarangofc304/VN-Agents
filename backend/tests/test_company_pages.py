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
