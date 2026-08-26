"""
CRM campaign EDIT / STOP / DELETE tests (iteration 32).

Covers:
- module: routes/crm_campaigns.py
  * PUT  /api/crm/campaigns/{id}  -> update name/direct_message/invite_note/daily_limit
  * PUT  /api/crm/campaigns/{id}  -> 404 unknown, 400 empty body, auth required
  * create -> edit -> GET roundtrip persistence (incl. long / non-truncated messages)
  * POST /api/crm/campaigns/{id}/stop -> status paused
  * DELETE /api/crm/campaigns/{id}   -> campaign + prospects removed
  * _send_message_or_invite -> cookie_expired_401 on auth failures (httpx mocked)
"""
import os
import sys
import asyncio

import pytest
import requests
from dotenv import dotenv_values

sys.path.insert(0, "/app/backend")

for _k, _v in dotenv_values("/app/backend/.env").items():
    if _v is not None:
        os.environ.setdefault(_k, _v)

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

SUPER_ADMIN = {"email": "vineet@channelloyalty.ai", "password": "CRM@2026!"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/crm-auth/login", json=SUPER_ADMIN)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("token")
    assert token, "no token in login response"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture
def new_campaign(client):
    created = []

    def _make(**over):
        payload = {
            "name": "TEST_QA_edit",
            "direct_message": "Hi {name}, saw you are {title} at {company}.",
            "invite_note": "Hi {name}, lets connect",
            "daily_limit": 10,
        }
        payload.update(over)
        r = client.post(f"{BASE_URL}/api/crm/campaigns", json=payload)
        assert r.status_code == 200, r.text
        cid = r.json()["campaign_id"]
        created.append(cid)
        return cid, payload

    yield _make
    for cid in created:
        client.delete(f"{BASE_URL}/api/crm/campaigns/{cid}")


# ---------------- PUT /campaigns/{id} ----------------
class TestCampaignEdit:
    def test_edit_all_fields_roundtrip(self, client, new_campaign):
        cid, _ = new_campaign()
        upd = {
            "name": "TEST_QA_edit_renamed",
            "direct_message": "Updated DM for {name} at {company} - lets talk about pricing.",
            "invite_note": "Updated invite for {name}",
            "daily_limit": 33,
        }
        r = client.put(f"{BASE_URL}/api/crm/campaigns/{cid}", json=upd)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True

        g = client.get(f"{BASE_URL}/api/crm/campaigns/{cid}")
        assert g.status_code == 200, g.text
        d = g.json()
        assert d["name"] == upd["name"]
        assert d["direct_message"] == upd["direct_message"]
        assert d["invite_note"] == upd["invite_note"]
        assert d["daily_limit"] == 33
        assert d["status"] == "active"
        assert "_id" not in d

    def test_edit_partial_leaves_other_fields(self, client, new_campaign):
        cid, orig = new_campaign()
        r = client.put(f"{BASE_URL}/api/crm/campaigns/{cid}", json={"name": "TEST_QA_only_name"})
        assert r.status_code == 200, r.text
        d = client.get(f"{BASE_URL}/api/crm/campaigns/{cid}").json()
        assert d["name"] == "TEST_QA_only_name"
        assert d["direct_message"] == orig["direct_message"]
        assert d["invite_note"] == orig["invite_note"]
        assert d["daily_limit"] == orig["daily_limit"]

    def test_edit_reflected_in_list(self, client, new_campaign):
        cid, _ = new_campaign()
        client.put(f"{BASE_URL}/api/crm/campaigns/{cid}", json={"name": "TEST_QA_list_check"})
        lst = client.get(f"{BASE_URL}/api/crm/campaigns").json()["campaigns"]
        match = [c for c in lst if c["campaign_id"] == cid]
        assert match, "edited campaign missing from list"
        assert match[0]["name"] == "TEST_QA_list_check"
        for key in ("total", "sent", "failed", "pending"):
            assert key in match[0]

    def test_daily_limit_capped_at_50(self, client, new_campaign):
        cid, _ = new_campaign()
        r = client.put(f"{BASE_URL}/api/crm/campaigns/{cid}", json={"daily_limit": 900})
        assert r.status_code == 200, r.text
        assert client.get(f"{BASE_URL}/api/crm/campaigns/{cid}").json()["daily_limit"] == 50

    def test_long_direct_message_not_truncated(self, client, new_campaign):
        cid, _ = new_campaign()
        long_msg = "Hi {name}, " + ("this is a long outreach message. " * 60)
        r = client.put(f"{BASE_URL}/api/crm/campaigns/{cid}", json={"direct_message": long_msg})
        assert r.status_code == 200, r.text
        stored = client.get(f"{BASE_URL}/api/crm/campaigns/{cid}").json()["direct_message"]
        assert stored == long_msg
        assert len(stored) == len(long_msg)

    def test_edit_unknown_campaign_404(self, client):
        r = client.put(f"{BASE_URL}/api/crm/campaigns/nope1234", json={"name": "x"})
        assert r.status_code == 404

    def test_edit_empty_body_400(self, client, new_campaign):
        cid, _ = new_campaign()
        r = client.put(f"{BASE_URL}/api/crm/campaigns/{cid}", json={})
        assert r.status_code == 400, r.text

    def test_edit_unknown_keys_only_400(self, client, new_campaign):
        cid, _ = new_campaign()
        r = client.put(f"{BASE_URL}/api/crm/campaigns/{cid}", json={"bogus": 1})
        assert r.status_code == 400, r.text

    def test_edit_requires_auth(self, client, new_campaign):
        cid, _ = new_campaign()
        r = requests.put(f"{BASE_URL}/api/crm/campaigns/{cid}", json={"name": "hack"})
        assert r.status_code == 401

    def test_edit_status_to_active_resumes(self, client, new_campaign):
        cid, _ = new_campaign()
        assert client.post(f"{BASE_URL}/api/crm/campaigns/{cid}/stop").status_code == 200
        assert client.get(f"{BASE_URL}/api/crm/campaigns/{cid}").json()["status"] == "paused"
        r = client.put(f"{BASE_URL}/api/crm/campaigns/{cid}", json={"status": "active"})
        assert r.status_code == 200, r.text
        assert client.get(f"{BASE_URL}/api/crm/campaigns/{cid}").json()["status"] == "active"


# ---------------- stop / delete ----------------
class TestStopDelete:
    def test_stop_sets_paused(self, client, new_campaign):
        cid, _ = new_campaign()
        r = client.post(f"{BASE_URL}/api/crm/campaigns/{cid}/stop")
        assert r.status_code == 200, r.text
        assert client.get(f"{BASE_URL}/api/crm/campaigns/{cid}").json()["status"] == "paused"

    def test_delete_removes_campaign(self, client, new_campaign):
        cid, _ = new_campaign()
        assert client.delete(f"{BASE_URL}/api/crm/campaigns/{cid}").status_code == 200
        assert client.get(f"{BASE_URL}/api/crm/campaigns/{cid}").status_code == 404
        lst = client.get(f"{BASE_URL}/api/crm/campaigns").json()["campaigns"]
        assert not [c for c in lst if c["campaign_id"] == cid]

    def test_delete_unknown_404(self, client):
        assert client.delete(f"{BASE_URL}/api/crm/campaigns/nope1234").status_code == 404

    def test_delete_removes_prospects(self, client, new_campaign):
        """Delete must cascade to crm_prospects (verified directly in Mongo)."""
        from motor.motor_asyncio import AsyncIOMotorClient
        cid, _ = new_campaign()
        db_url = os.environ["MONGO_URL"]
        db_name = os.environ["DB_NAME"]

        async def seed_and_check():
            cl = AsyncIOMotorClient(db_url)
            db = cl[db_name]
            await db.crm_prospects.insert_many([
                {"campaign_id": cid, "rank": 1, "name": "TEST_QA P1",
                 "public_id": "test-qa-p1", "status": "pending"},
                {"campaign_id": cid, "rank": 2, "name": "TEST_QA P2",
                 "public_id": "test-qa-p2", "status": "pending"},
            ])
            before = await db.crm_prospects.count_documents({"campaign_id": cid})
            return cl, db, before

        loop = asyncio.new_event_loop()
        cl, db, before = loop.run_until_complete(seed_and_check())
        assert before == 2

        detail = client.get(f"{BASE_URL}/api/crm/campaigns/{cid}").json()
        assert len(detail["prospects"]) == 2

        assert client.delete(f"{BASE_URL}/api/crm/campaigns/{cid}").status_code == 200
        after = loop.run_until_complete(db.crm_prospects.count_documents({"campaign_id": cid}))
        loop.run_until_complete(db.crm_prospects.delete_many({"campaign_id": cid}))
        cl.close()
        loop.close()
        assert after == 0, f"{after} orphaned prospects left after campaign delete"


# ---------------- _send_message_or_invite auth-error surfacing (mocked) ----------------
class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, post_handler):
        self._post = post_handler
        self.calls = []

    async def get(self, url, headers=None, **kw):
        return _FakeResp(404)

    async def post(self, url, json=None, headers=None, **kw):
        self.calls.append(url)
        return self._post(url, json)


@pytest.fixture(scope="module")
def crm_mod():
    import routes.crm_campaigns as mod
    return mod


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestSendAuthErrors:
    def test_401_on_invite_returns_cookie_expired(self, crm_mod):
        c = _FakeClient(lambda url, body: _FakeResp(401))
        ok, reason = _run(crm_mod._send_message_or_invite(
            c, {}, "urn:li:fsd_profile:ACoAAA1", "john-doe", "hi", "hello"))
        assert ok is False
        assert reason == "cookie_expired_401", f"got {reason}"

    def test_401_without_urn_returns_cookie_expired(self, crm_mod):
        c = _FakeClient(lambda url, body: _FakeResp(401))
        ok, reason = _run(crm_mod._send_message_or_invite(
            c, {}, None, "john-doe", "hi", "hello"))
        assert ok is False
        assert reason == "cookie_expired_401", f"got {reason}"

    def test_999_challenge_reports_status(self, crm_mod):
        c = _FakeClient(lambda url, body: _FakeResp(999))
        ok, reason = _run(crm_mod._send_message_or_invite(
            c, {}, None, "john-doe", "hi", "hello"))
        assert ok is False
        assert reason == "send_failed_999", f"got {reason}"

    def test_message_sent_when_conversation_created(self, crm_mod):
        c = _FakeClient(lambda url, body: _FakeResp(201) if "messaging/conversations" in url else _FakeResp(400))
        ok, reason = _run(crm_mod._send_message_or_invite(
            c, {}, "urn:li:fsd_profile:ACoAAA1", "john-doe", "hi there", "hello"))
        assert ok is True and reason == "message_sent"

    def test_full_message_body_sent_not_truncated(self, crm_mod):
        """Direct message must be sent in full (no 300-char truncation)."""
        captured = {}

        def handler(url, body):
            captured["body"] = body
            return _FakeResp(201)

        c = _FakeClient(handler)
        long_msg = "A" * 900
        ok, reason = _run(crm_mod._send_message_or_invite(
            c, {}, "urn:li:fsd_profile:ACoAAA1", "john-doe", long_msg, "note"))
        assert ok is True
        create = captured["body"]["conversationCreate"]["eventCreate"]["value"][
            "com.linkedin.voyager.messaging.create.MessageCreate"]
        assert create["body"] == long_msg
        assert create["attributedBody"]["text"] == long_msg

    def test_invite_note_capped_at_300(self, crm_mod):
        captured = []

        def handler(url, body):
            captured.append(body)
            return _FakeResp(201) if "verifyQuotaAndCreate" in url else _FakeResp(400)

        c = _FakeClient(handler)
        ok, reason = _run(crm_mod._send_message_or_invite(
            c, {}, None, "john-doe", "", "B" * 500))
        assert ok is True and reason == "invite_sent"
        assert len(captured[-1]["customMessage"]) == 300
