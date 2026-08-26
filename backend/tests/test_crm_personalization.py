"""
CRM connections + campaign personalization tests (iteration 31).

Covers:
- module: routes/crm_campaigns.py
  * GET /api/crm/connections response structure + occupation -> company/title parsing (httpx mocked)
  * POST /api/crm/connections/message  {name}/{company}/{title} replacement (httpx mocked)
  * campaign batch personalization (_send_batch_bg)
  * Campaign CRUD over public URL: create (direct_message + invite_note), get, stop, delete
"""
import os
import sys
import types
import asyncio
import uuid

import pytest
import requests
from dotenv import dotenv_values

sys.path.insert(0, "/app/backend")

# backend env needed for direct module imports (MONGO_URL / DB_NAME)
for _k, _v in dotenv_values("/app/backend/.env").items():
    if _v is not None:
        os.environ.setdefault(_k, _v)

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

SUPER_ADMIN = {"email": "vineet@channelloyalty.ai", "password": "CRM@2026!"}


# ---------------- HTTP fixtures ----------------
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


@pytest.fixture(scope="module")
def campaign(client):
    payload = {
        "name": "TEST_QA_personalization",
        "direct_message": "Hi {name}, saw you are {title} at {company}. Lets chat!",
        "invite_note": "Hi {name}, connecting re {company}",
        "daily_limit": 10,
    }
    r = client.post(f"{BASE_URL}/api/crm/campaigns", json=payload)
    assert r.status_code == 200, r.text
    cid = r.json()["campaign_id"]
    yield cid, payload
    client.delete(f"{BASE_URL}/api/crm/campaigns/{cid}")


# ---------------- Campaign CRUD / stop / delete ----------------
class TestCampaignCRUD:
    def test_create_persists_templates(self, client, campaign):
        cid, payload = campaign
        r = client.get(f"{BASE_URL}/api/crm/campaigns/{cid}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["direct_message"] == payload["direct_message"]
        assert d["invite_note"] == payload["invite_note"]
        assert d["status"] == "active"
        assert d["daily_limit"] == 10
        assert isinstance(d["prospects"], list)
        assert "_id" not in d

    def test_stop_sets_paused(self, client, campaign):
        cid, _ = campaign
        r = client.post(f"{BASE_URL}/api/crm/campaigns/{cid}/stop")
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True
        assert client.get(f"{BASE_URL}/api/crm/campaigns/{cid}").json()["status"] == "paused"

    def test_stop_unknown_campaign_404(self, client):
        r = client.post(f"{BASE_URL}/api/crm/campaigns/nope1234/stop")
        assert r.status_code == 404

    def test_delete_removes_campaign_and_prospects(self, client):
        r = client.post(f"{BASE_URL}/api/crm/campaigns", json={
            "name": "TEST_QA_delete", "direct_message": "hi {name}", "invite_note": ""})
        cid = r.json()["campaign_id"]
        d = client.delete(f"{BASE_URL}/api/crm/campaigns/{cid}")
        assert d.status_code == 200, d.text
        assert client.get(f"{BASE_URL}/api/crm/campaigns/{cid}").status_code == 404

    def test_delete_unknown_campaign_404(self, client):
        assert client.delete(f"{BASE_URL}/api/crm/campaigns/nope1234").status_code == 404


# ---------------- Connections message validation (no LinkedIn call needed) ----------------
class TestConnectionsMessageValidation:
    def test_no_recipients_400(self, client):
        r = client.post(f"{BASE_URL}/api/crm/connections/message", json={"recipients": [], "message": "hi"})
        assert r.status_code == 400

    def test_no_message_400(self, client):
        r = client.post(f"{BASE_URL}/api/crm/connections/message",
                        json={"recipients": [{"publicId": "x", "name": "A B", "urn": "urn:li:fsd_profile:123"}], "message": ""})
        assert r.status_code == 400

    def test_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/crm/connections/message", json={"recipients": [], "message": "hi"})
        assert r.status_code == 401

    def test_connections_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/crm/connections").status_code == 401


# ---------------- Unit tests with mocked LinkedIn (httpx) ----------------
class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _FakeClient:
    """Captures GET/POST calls and returns scripted responses."""

    def __init__(self, get_handler=None, post_handler=None, sink=None):
        self._get = get_handler
        self._post = post_handler
        self.sink = sink if sink is not None else []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None, **kw):
        return self._get(url) if self._get else _FakeResp(404)

    async def post(self, url, json=None, headers=None, **kw):
        self.sink.append({"url": url, "json": json})
        return self._post(url, json) if self._post else _FakeResp(201)


def _fake_request():
    req = types.SimpleNamespace()
    req._json = {}

    async def json():
        return req._json
    req.json = json
    return req


@pytest.fixture
def crm_mod(monkeypatch):
    import routes.crm_campaigns as mod

    async def fake_user(request):
        return {"id": "u1", "email": "qa@test.local", "name": "QA"}

    async def fake_cookies(user):
        return "li_at_val", "jsess_val"

    async def no_sleep(*a, **k):
        return None

    monkeypatch.setattr(mod, "get_current_user", fake_user)
    monkeypatch.setattr(mod, "_get_user_cookies", fake_cookies)
    monkeypatch.setattr(mod.asyncio, "sleep", no_sleep)
    return mod


CONNECTIONS_PAYLOAD = {
    "included": [
        {
            "entityUrn": "urn:li:fsd_profile:ACoAAA111",
            "firstName": "Asha",
            "lastName": "Rao",
            "occupation": "VP Marketing at Acme Corp",
            "publicIdentifier": "asha-rao",
            "locationName": "Mumbai, India",
        },
        {
            "entityUrn": "urn:li:fsd_profile:ACoAAA222",
            "firstName": "Bob",
            "lastName": "Singh",
            "occupation": "Founder @ Zeta Labs",
            "publicIdentifier": "bob-singh",
            "locationName": "Delhi, India",
        },
        {
            "entityUrn": "urn:li:fsd_profile:ACoAAA333",
            "firstName": "Cara",
            "lastName": "Lee",
            "occupation": "Independent Consultant",
            "publicIdentifier": "cara-lee",
        },
        {"entityUrn": "urn:li:fsd_something:1", "someOther": "entity"},
    ],
    "paging": {"total": 3},
}


class TestConnectionsStructure:
    def test_connections_fields_and_company_parsing(self, crm_mod, monkeypatch):
        def get_handler(url):
            if "profileContactInfo" in url:
                pid = url.split("/profiles/")[1].split("/")[0]
                if pid == "asha-rao":
                    return _FakeResp(200, {"emailAddress": "asha@acme.com",
                                           "phoneNumbers": [{"number": "+911234567890"}]})
                return _FakeResp(404)
            if "relationships/dash/connections" in url:
                return _FakeResp(200, CONNECTIONS_PAYLOAD)
            return _FakeResp(404)

        monkeypatch.setattr(crm_mod.httpx, "AsyncClient",
                            lambda *a, **k: _FakeClient(get_handler=get_handler))

        out = asyncio.get_event_loop().run_until_complete(
            crm_mod.get_connections(_fake_request(), count=50, start=0))

        conns = out["connections"]
        assert out["total"] == 3
        assert len(conns) == 3, f"expected 3 people, got {[c['name'] for c in conns]}"

        required = {"name", "company", "title", "email", "phone", "location",
                    "linkedinUrl", "urn", "publicIdentifier", "headline"}
        for c in conns:
            assert required.issubset(c.keys()), f"missing: {required - set(c.keys())}"

        a = conns[0]
        assert a["name"] == "Asha Rao"
        assert a["title"] == "VP Marketing"
        assert a["company"] == "Acme Corp"
        assert a["location"] == "Mumbai, India"
        assert a["linkedinUrl"] == "https://linkedin.com/in/asha-rao"
        assert a["urn"] == "urn:li:fsd_profile:ACoAAA111"
        assert a["email"] == "asha@acme.com"
        assert a["phone"] == "+911234567890"

        b = conns[1]
        assert b["title"] == "Founder" and b["company"] == "Zeta Labs"

        c = conns[2]
        assert c["title"] == "Independent Consultant" and c["company"] == ""
        assert c["email"] == "" and c["phone"] == "" and c["location"] == ""

    def test_connections_upstream_error_is_502(self, crm_mod, monkeypatch):
        monkeypatch.setattr(crm_mod.httpx, "AsyncClient",
                            lambda *a, **k: _FakeClient(get_handler=lambda u: _FakeResp(999)))
        with pytest.raises(crm_mod.HTTPException) as ei:
            asyncio.get_event_loop().run_until_complete(
                crm_mod.get_connections(_fake_request(), count=10, start=0))
        assert ei.value.status_code == 502


class TestMessagePersonalization:
    def test_connections_message_replaces_placeholders(self, crm_mod, monkeypatch):
        sink = []
        monkeypatch.setattr(crm_mod.httpx, "AsyncClient",
                            lambda *a, **k: _FakeClient(post_handler=lambda u, j: _FakeResp(201), sink=sink))

        req = _fake_request()
        req._json = {
            "message": "Hi {name}, how is {title} life at {company}?",
            "recipients": [
                {"publicId": "asha-rao", "name": "Asha Rao", "urn": "urn:li:fsd_profile:ACoAAA111",
                 "company": "Acme Corp", "title": "VP Marketing"},
                {"publicId": "no-urn", "name": "No Urn", "urn": "", "company": "X", "title": "Y"},
                {"publicId": "cara", "name": "Cara Lee", "urn": "urn:li:fsd_profile:ACoAAA333",
                 "company": "", "title": ""},
            ],
        }
        out = asyncio.get_event_loop().run_until_complete(crm_mod.message_connections(req))

        assert out["total"] == 3
        assert out["sent"] == 2
        statuses = {r["name"]: r["status"] for r in out["results"]}
        assert statuses["Asha Rao"] == "sent"
        assert statuses["No Urn"] == "skipped"

        bodies = []
        for call in sink:
            ev = call["json"]["conversationCreate"]["eventCreate"]["value"]["com.linkedin.voyager.messaging.create.MessageCreate"]
            bodies.append(ev["attributedBody"]["text"])
        assert bodies[0] == "Hi Asha, how is VP Marketing life at Acme Corp?"
        assert "{company}" not in bodies[0] and "{name}" not in bodies[0]
        # empty company must fall back, never leave the raw token
        assert "{company}" not in bodies[1]
        assert "your company" in bodies[1]

        # recipient URN -> member id used for delivery
        assert sink[0]["json"]["conversationCreate"]["recipients"] == ["ACoAAA111"]

    def test_campaign_batch_personalization(self, crm_mod, monkeypatch):
        captured = []

        async def fake_resolve(client, pid, headers):
            return f"urn:li:fsd_profile:{pid}", None

        async def fake_send(client, headers, urn, pid, direct, invite):
            captured.append({"pid": pid, "direct": direct, "invite": invite})
            return True, "message_sent"

        class _DB:
            class _Coll:
                def __init__(self, doc=None):
                    self.doc = doc

                async def find_one(self, *a, **k):
                    return self.doc

                async def update_one(self, *a, **k):
                    return None
            crm_campaigns = _Coll({"campaign_id": "c1", "status": "active"})
            crm_prospects = _Coll(None)

        monkeypatch.setattr(crm_mod, "_resolve_urn", fake_resolve)
        monkeypatch.setattr(crm_mod, "_send_message_or_invite", fake_send)
        monkeypatch.setattr(crm_mod, "_db", _DB)
        monkeypatch.setattr(crm_mod.httpx, "AsyncClient", lambda *a, **k: _FakeClient())

        campaign = {
            "campaign_id": "c1",
            "direct_message": "Hey {name}, {title} at {company} right?",
            "invite_note": "Hi {name} from {company}",
        }
        prospects = [
            {"name": "Asha Rao", "company": "Acme Corp", "title": "VP Marketing", "public_id": "asha-rao"},
            {"name": "Nocompany Guy", "company": "", "title": "", "public_id": "nc"},
        ]
        asyncio.get_event_loop().run_until_complete(
            crm_mod._send_batch_bg(campaign, prospects, {}))

        assert captured[0]["direct"] == "Hey Asha, VP Marketing at Acme Corp right?"
        assert captured[0]["invite"] == "Hi Asha from Acme Corp"
        assert "{company}" not in captured[1]["direct"]
        assert "your company" in captured[1]["direct"]
