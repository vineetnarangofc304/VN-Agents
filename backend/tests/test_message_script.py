"""Tests for POST /api/li-search/message/script and regressions."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # fallback: read from frontend/.env
    from pathlib import Path
    env_file = Path('/app/frontend/.env')
    for line in env_file.read_text().splitlines():
        if line.startswith('REACT_APP_BACKEND_URL='):
            BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
            break

SCRIPT_URL = f"{BASE_URL}/api/li-search/message/script"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestMessageScript:
    """POST /api/li-search/message/script"""

    def test_generate_script_valid(self, client):
        recipients = [
            {"name": "Alice TestUser", "profile_url": "https://www.linkedin.com/in/alice-test/", "public_id": "alice-test"},
            {"name": "Bob TestUser", "profile_url": "https://www.linkedin.com/in/bob-test/", "public_id": "bob-test"},
        ]
        msg = "Hi there, would love to connect!"
        r = client.post(SCRIPT_URL, json={"recipients": recipients, "message": msg})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "script" in data and isinstance(data["script"], str)
        assert data.get("recipients_count") == 2
        script = data["script"]
        # Message and recipients embedded
        assert msg in script
        assert "Alice TestUser" in script
        assert "Bob TestUser" in script
        assert "alice-test" in script
        assert "bob-test" in script

    def test_empty_recipients_returns_400(self, client):
        r = client.post(SCRIPT_URL, json={"recipients": [], "message": "hi"})
        assert r.status_code == 400

    def test_empty_message_returns_400(self, client):
        r = client.post(SCRIPT_URL, json={"recipients": [{"name": "X", "profile_url": "u", "public_id": "x"}], "message": ""})
        assert r.status_code == 400

    def test_missing_both_returns_400(self, client):
        r = client.post(SCRIPT_URL, json={})
        assert r.status_code == 400

    def test_script_escapes_backticks(self, client):
        r = client.post(SCRIPT_URL, json={
            "recipients": [{"name": "T", "profile_url": "u", "public_id": "t"}],
            "message": "Hello `world` ${foo}"
        })
        assert r.status_code == 200
        script = r.json()["script"]
        # backticks must be escaped so the template literal is intact
        assert "\\`world\\`" in script or "\\`" in script
        assert "\\${foo}" in script


class TestRegressions:
    def test_health(self, client):
        r = client.get(f"{BASE_URL}/api/health")
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"

    def test_posts_returns_at_least_20(self, client):
        r = client.get(f"{BASE_URL}/api/li-search/posts?limit=50")
        assert r.status_code == 200
        data = r.json()
        assert "posts" in data
        assert len(data["posts"]) >= 20, f"only {len(data['posts'])} posts"
