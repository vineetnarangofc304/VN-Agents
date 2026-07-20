"""Backend tests for Content Studio (Agent 9)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://automation-platform-10.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api/content-studio"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# Pillars
def test_get_pillars(s):
    r = s.get(f"{API}/pillars", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "pillars" in data
    assert len(data["pillars"]) == 18
    assert all("id" in p and "name" in p and "color" in p for p in data["pillars"])


# Stats
def test_get_stats(s):
    r = s.get(f"{API}/stats", timeout=15)
    assert r.status_code == 200
    d = r.json()
    for k in ["total_posts", "published", "drafts", "scheduled", "this_week", "pillar_distribution"]:
        assert k in d
    assert isinstance(d["total_posts"], int)


# Posts list
def test_get_posts_list(s):
    r = s.get(f"{API}/posts", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "posts" in d and "total" in d
    assert isinstance(d["posts"], list)


def test_get_posts_with_filters(s):
    r = s.get(f"{API}/posts?status=draft&limit=5", timeout=15)
    assert r.status_code == 200
    assert "posts" in r.json()


# Calendar list
def test_get_calendar(s):
    r = s.get(f"{API}/calendar", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "calendar" in d
    assert isinstance(d["calendar"], list)


# OAuth status
def test_oauth_status(s):
    r = s.get(f"{API}/oauth/status", timeout=15)
    assert r.status_code == 200
    assert "connected" in r.json()


# Generation pipeline
def test_generate_content_pipeline(s):
    r = s.post(f"{API}/generate", json={
        "pillar": "enterprise-ai",
        "content_type": "linkedin-post",
        "topic_hint": "TEST_ AI adoption in enterprise"
    }, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "post_id" in d
    assert d.get("status") == "generating"
    post_id = d["post_id"]

    # Poll status - takes 15-25 seconds
    final = None
    for _ in range(40):
        time.sleep(2)
        sr = s.get(f"{API}/posts/{post_id}/status", timeout=15)
        assert sr.status_code == 200
        sd = sr.json()
        if sd.get("status") in ("draft", "error"):
            final = sd
            break
    assert final is not None, "Generation timed out"
    assert final["status"] == "draft", f"Generation failed: {final.get('error')}"
    assert final.get("content"), "No content generated"
    assert isinstance(final.get("quality_score"), (int, float))

    # Verify persisted via list
    lr = s.get(f"{API}/posts?limit=50", timeout=15)
    ids = [p["post_id"] for p in lr.json()["posts"]]
    assert post_id in ids

    # Cleanup
    s.delete(f"{API}/posts/{post_id}", timeout=15)


# Calendar generate (7 days for speed)
def test_generate_calendar(s):
    r = s.post(f"{API}/calendar/generate", json={"days": 7}, timeout=90)
    assert r.status_code == 200
    d = r.json()
    assert d.get("success") is True, f"Calendar gen failed: {d}"
    assert d.get("days", 0) >= 5
    assert isinstance(d.get("calendar"), list)
    item = d["calendar"][0]
    for k in ["pillar", "topic", "content_type"]:
        assert k in item


# Message generate (from LinkedIn Lead Finder) - check if endpoint exists
def test_linkedin_message_generate():
    # Endpoint is /api/linkedin/message/generate or /api/content-studio/message/generate
    r = requests.post(f"{BASE_URL}/api/li-search/message/generate", json={
        "recipient_name": "John Doe",
        "recipient_title": "CTO",
        "company": "fundle",
        "purpose": "introduce our AI platform"
    }, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("success") is True
    assert d.get("message")
