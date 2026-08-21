"""
Tests for the LinkedIn Outreach Campaign Manager (routes/campaign_manager.py)
Covers: campaign list, prospect list, campaign create, send-batch error handling.
NOTE: send-batch is only exercised against campaigns with ZERO pending prospects,
so no real LinkedIn message is ever sent.
"""
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL is missing")
BASE_URL = base_url.rstrip("/")

MYNTRA_CAMPAIGN_ID = "7701ea79"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def created_campaign_ids():
    return []


# ---------- module: campaign listing ----------
class TestCampaignList:
    def test_list_campaigns(self, api):
        r = api.get(f"{BASE_URL}/api/campaigns", timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "campaigns" in data and isinstance(data["campaigns"], list)
        assert len(data["campaigns"]) >= 1

        c = next((x for x in data["campaigns"] if x["campaign_id"] == MYNTRA_CAMPAIGN_ID), None)
        assert c is not None, "Myntra 500 campaign 7701ea79 missing"
        assert "_id" not in c
        assert c["total"] == 91, f"expected 91 total, got {c['total']}"
        assert c["pending"] == 91, f"expected 91 pending, got {c['pending']}"
        assert c["sent"] == 0
        assert c["failed"] == 0
        assert c["status"] == "active"
        assert c["daily_limit"] == 25
        # message template must carry both personalisation placeholders
        assert "{name}" in c["message_template"]
        assert "{brand}" in c["message_template"]


# ---------- module: prospects ----------
class TestProspects:
    def test_get_prospects_default_limit(self, api):
        r = api.get(f"{BASE_URL}/api/campaigns/{MYNTRA_CAMPAIGN_ID}/prospects", timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["total"] == 91
        assert len(data["prospects"]) == 50, "default limit should cap at 50"
        p = data["prospects"][0]
        for key in ("name", "brand", "linkedin_url", "public_id", "status", "rank", "title"):
            assert key in p, f"missing field {key}"
        assert "_id" not in p
        assert p["status"] == "pending"
        assert "linkedin.com" in p["linkedin_url"]
        assert p["name"].strip() != ""
        assert p["brand"].strip() != ""
        # sorted by rank ascending
        ranks = [x["rank"] for x in data["prospects"]]
        assert ranks == sorted(ranks)

    def test_get_prospects_full_and_status_filter(self, api):
        r = api.get(f"{BASE_URL}/api/campaigns/{MYNTRA_CAMPAIGN_ID}/prospects?limit=200", timeout=60)
        assert r.status_code == 200
        allp = r.json()["prospects"]
        assert len(allp) == 91
        # all have a resolvable public_id and unique
        ids = [p["public_id"] for p in allp]
        assert all(ids)
        assert len(set(ids)) == 91, "duplicate public_ids imported"

        r2 = api.get(f"{BASE_URL}/api/campaigns/{MYNTRA_CAMPAIGN_ID}/prospects?status=pending&limit=200", timeout=60)
        assert r2.status_code == 200
        assert r2.json()["total"] == 91

        r3 = api.get(f"{BASE_URL}/api/campaigns/{MYNTRA_CAMPAIGN_ID}/prospects?status=sent", timeout=60)
        assert r3.status_code == 200
        assert r3.json()["total"] == 0
        assert r3.json()["prospects"] == []

    def test_prospects_unknown_campaign_returns_empty(self, api):
        r = api.get(f"{BASE_URL}/api/campaigns/does-not-exist/prospects", timeout=60)
        # documents current behaviour: empty list, not 404
        assert r.status_code == 200
        assert r.json()["total"] == 0


# ---------- module: campaign create ----------
class TestCampaignCreate:
    def test_create_campaign_and_verify_persistence(self, api, created_campaign_ids):
        payload = {
            "name": "TEST_qa_campaign",
            "message_template": "Hi {name} from {brand}",
            "sender_name": "QA",
            "daily_limit": 5,
        }
        r = api.post(f"{BASE_URL}/api/campaigns", json=payload, timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["success"] is True
        cid = body["campaign_id"]
        assert isinstance(cid, str) and len(cid) == 8
        created_campaign_ids.append(cid)

        listing = api.get(f"{BASE_URL}/api/campaigns", timeout=60).json()["campaigns"]
        created = next((c for c in listing if c["campaign_id"] == cid), None)
        assert created is not None, "created campaign not persisted"
        assert created["name"] == "TEST_qa_campaign"
        assert created["message_template"] == "Hi {name} from {brand}"
        assert created["sender_name"] == "QA"
        assert created["daily_limit"] == 5
        assert created["total"] == 0 and created["pending"] == 0

    def test_create_campaign_empty_body_uses_defaults(self, api, created_campaign_ids):
        r = api.post(f"{BASE_URL}/api/campaigns", json={}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        cid = r.json()["campaign_id"]
        created_campaign_ids.append(cid)
        listing = api.get(f"{BASE_URL}/api/campaigns", timeout=60).json()["campaigns"]
        c = next(x for x in listing if x["campaign_id"] == cid)
        assert c["name"] == "Untitled Campaign"
        assert c["daily_limit"] == 25


# ---------- module: send-batch error handling (no real sends) ----------
class TestSendBatch:
    def test_send_batch_unknown_campaign_404(self, api):
        r = api.post(f"{BASE_URL}/api/campaigns/nope1234/send-batch", json={"batch_size": 1}, timeout=90)
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text[:300]}"
        assert "not found" in r.json()["detail"].lower()

    def test_send_batch_no_pending_returns_graceful_response(self, api, created_campaign_ids):
        # Use a freshly created campaign with 0 prospects -> must not crash, must not call LinkedIn
        r = api.post(f"{BASE_URL}/api/campaigns", json={"name": "TEST_qa_empty"}, timeout=60)
        cid = r.json()["campaign_id"]
        created_campaign_ids.append(cid)

        r2 = api.post(f"{BASE_URL}/api/campaigns/{cid}/send-batch", json={"batch_size": 1}, timeout=90)
        assert r2.status_code in (200, 400), r2.text[:300]
        body = r2.json()
        if r2.status_code == 400:
            # acceptable: cookie missing/expired -> explicit 400, never a 500
            assert "cookie" in body["detail"].lower() or "JSESSIONID" in body["detail"]
        else:
            assert body.get("sent") == 0
            assert "pending" in str(body.get("detail", "")).lower()

    def test_send_batch_never_returns_500(self, api, created_campaign_ids):
        r = api.post(f"{BASE_URL}/api/campaigns", json={"name": "TEST_qa_empty2"}, timeout=60)
        cid = r.json()["campaign_id"]
        created_campaign_ids.append(cid)
        r2 = api.post(f"{BASE_URL}/api/campaigns/{cid}/send-batch", json={}, timeout=90)
        assert r2.status_code < 500, f"server error: {r2.status_code} {r2.text[:300]}"


# ---------- module: attachment / assets ----------
class TestAssets:
    def test_brochure_attachment_exists(self, api):
        listing = api.get(f"{BASE_URL}/api/campaigns", timeout=60).json()["campaigns"]
        c = next(x for x in listing if x["campaign_id"] == MYNTRA_CAMPAIGN_ID)
        path = c.get("attachment_path", "")
        assert path, "campaign has no attachment_path"
        assert Path(path).exists(), f"attachment file missing on disk: {path}"
        assert Path(path).stat().st_size > 1000

    def test_import_prospects_requires_file(self, api, created_campaign_ids):
        r = api.post(f"{BASE_URL}/api/campaigns", json={"name": "TEST_qa_import"}, timeout=60)
        cid = r.json()["campaign_id"]
        created_campaign_ids.append(cid)
        r2 = api.post(f"{BASE_URL}/api/campaigns/{cid}/import-prospects", timeout=120)
        assert r2.status_code in (200, 400), r2.text[:300]

    def test_import_prospects_unknown_campaign_404(self, api):
        r = api.post(f"{BASE_URL}/api/campaigns/zzz99999/import-prospects", timeout=60)
        assert r.status_code == 404


# ---------- cleanup ----------
@pytest.fixture(scope="module", autouse=True)
def cleanup(created_campaign_ids):
    yield
    if not created_campaign_ids:
        return
    from pymongo import MongoClient
    env = dotenv_values("/app/backend/.env")
    mc = MongoClient(env.get("MONGO_URL"))
    dbn = env.get("DB_NAME")
    mc[dbn].outreach_campaigns.delete_many({"campaign_id": {"$in": created_campaign_ids}})
    mc[dbn].campaign_prospects.delete_many({"campaign_id": {"$in": created_campaign_ids}})
    mc.close()
