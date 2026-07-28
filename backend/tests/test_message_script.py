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
        # New impl uses json.dumps (double-quoted string) so raw backticks/${ are fine
        assert '"Hello `world` ${foo}"' in script

    def test_script_special_chars_newlines_dollar_asterisk(self, client):
        """The bug: newlines, $, *, & in message crashed f-string. Must now succeed."""
        msg = "Hello Dr..\n\nI am the founder of HearClear.\n* AI-based screening\n* $100 & 50%"
        recipients = [
            {"name": "Dr. Test", "profile_url": "https://www.linkedin.com/in/dr-test/", "public_id": "dr-test"},
            {"name": "Second Dr", "profile_url": "https://www.linkedin.com/in/second-dr/", "public_id": "second-dr"},
        ]
        r = client.post(SCRIPT_URL, json={"recipients": recipients, "message": msg})
        assert r.status_code == 200, r.text
        data = r.json()
        script = data["script"]
        assert data["recipients_count"] == 2
        # json.dumps escapes newlines to \n and keeps $ * & as-is inside double quotes
        import json as _json
        assert _json.dumps(msg) in script
        # Ensure it's NOT a backtick template literal for message
        assert "`" + msg not in script


class TestTypeaheadURNLookupScript:
    """Verify the script does on-the-fly URN lookup via typeahead + faceted search."""

    def _get_script(self, client):
        r = client.post(SCRIPT_URL, json={
            "recipients": [
                {"name": "Alice", "profile_url": "https://www.linkedin.com/in/alice/", "public_id": "alice"},
                {"name": "Bob", "profile_url": "https://www.linkedin.com/in/bob/", "public_id": "bob"},
            ],
            "message": "Hello!"
        })
        assert r.status_code == 200, r.text
        return r.json()["script"]

    def test_uses_messaging_compose_typeahead(self, client):
        script = self._get_script(client)
        assert "voyagerSearchDashReusableTypeahead" in script
        assert "MESSAGING_COMPOSE" in script

    def test_has_faceted_search_fallback(self, client):
        script = self._get_script(client)
        assert "FACETED_SEARCH" in script
        assert "search/dash/clusters" in script

    def test_has_both_messaging_endpoints(self, client):
        script = self._get_script(client)
        # New endpoint
        assert "voyagerMessagingDashMessengerMessages?action=createMessage" in script
        # Old fallback endpoint
        assert "messaging/conversations?action=create" in script

    def test_does_not_require_pre_stored_urn(self, client):
        """Script should look up URN on the fly even if recipient has no entity_urn."""
        r = client.post(SCRIPT_URL, json={
            "recipients": [{"name": "NoUrn Person", "profile_url": "https://www.linkedin.com/in/no-urn/", "public_id": "no-urn"}],
            "message": "Hi"
        })
        assert r.status_code == 200
        script = r.json()["script"]
        # Must include on-the-fly lookup logic
        assert "voyagerSearchDashReusableTypeahead" in script
        # Must handle absence of entity_urn gracefully (uses rec.entity_urn || '')
        assert "rec.entity_urn" in script or "entity_urn" in script
        # Must match by publicIdentifier
        assert "publicIdentifier" in script

    def test_matches_by_public_identifier(self, client):
        script = self._get_script(client)
        assert "publicIdentifier" in script
        # Match logic present
        assert "fsd_profile" in script

    def test_multiline_special_chars(self, client):
        import json as _json
        msg = "Line1\nLine2\n* bullet\n$100 & 50% `code`"
        r = client.post(SCRIPT_URL, json={
            "recipients": [{"name": "T", "profile_url": "u", "public_id": "t"}],
            "message": msg
        })
        assert r.status_code == 200
        script = r.json()["script"]
        assert _json.dumps(msg) in script


class TestBrowserSyncScriptV7:
    """GET /api/li-search/browser-script — sync v7 with DOM scrape + typeahead URN enrichment."""

    def test_returns_v7_script(self, client):
        r = client.get(f"{BASE_URL}/api/li-search/browser-script")
        assert r.status_code == 200
        data = r.json()
        assert "script" in data
        assert "instructions" in data
        script = data["script"]
        assert "v7" in script or "Connection Sync v7" in script

    def test_v7_does_dom_scraping(self, client):
        r = client.get(f"{BASE_URL}/api/li-search/browser-script")
        script = r.json()["script"]
        # DOM scraping present
        assert "querySelectorAll" in script
        assert "/in/" in script

    def test_v7_does_typeahead_urn_lookup(self, client):
        r = client.get(f"{BASE_URL}/api/li-search/browser-script")
        script = r.json()["script"]
        assert "voyagerSearchDashReusableTypeahead" in script
        assert "MESSAGING_COMPOSE" in script
        assert "entity_urn" in script

    def test_v7_matches_by_public_identifier(self, client):
        r = client.get(f"{BASE_URL}/api/li-search/browser-script")
        script = r.json()["script"]
        assert "publicIdentifier" in script
        assert "fsd_profile" in script


class TestConnectionsPush:
    """POST /api/li-search/connections/push accepts and stores entity_urn."""

    def test_push_stores_entity_urn(self, client):
        payload = {
            "connections": [
                {
                    "full_name": "TEST_Push User",
                    "first_name": "TEST_Push",
                    "last_name": "User",
                    "occupation": "Tester",
                    "profile_url": "https://www.linkedin.com/in/test-push-user/",
                    "public_id": "test-push-user-urn",
                    "entity_urn": "urn:li:fsd_profile:ABC123TEST",
                    "avatar_url": "",
                }
            ]
        }
        r = client.post(f"{BASE_URL}/api/li-search/connections/push", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("success") is True
        assert data.get("stored") == 1

        # Verify persisted with entity_urn
        g = client.get(f"{BASE_URL}/api/li-search/connections?keyword=TEST_Push")
        assert g.status_code == 200
        conns = g.json().get("connections", [])
        match = [c for c in conns if c.get("public_id") == "test-push-user-urn"]
        assert len(match) == 1
        assert match[0].get("entity_urn") == "urn:li:fsd_profile:ABC123TEST"

    def test_push_empty_returns_400(self, client):
        r = client.post(f"{BASE_URL}/api/li-search/connections/push", json={"connections": []})
        assert r.status_code == 400


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
