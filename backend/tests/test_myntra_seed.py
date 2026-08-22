"""Tests for the auto-seeded Myntra 500 campaign (routes/campaign_manager.py seed_myntra_campaign)."""
import os
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
CID = "7701ea79"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---- Health ----
class TestHealth:
    def test_health(self, client):
        r = client.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data, dict)


# ---- Campaign listing / seed verification ----
class TestCampaignSeed:
    def test_list_campaigns_contains_myntra(self, client):
        r = client.get(f"{BASE_URL}/api/campaigns", timeout=60)
        assert r.status_code == 200, r.text[:300]
        campaigns = r.json()["campaigns"]
        assert len(campaigns) >= 1
        myntra = [c for c in campaigns if c["campaign_id"] == CID]
        assert myntra, f"Myntra campaign {CID} not seeded"
        c = myntra[0]
        assert "Myntra 500" in c["name"]
        assert c["total"] >= 76, f"expected >=76 prospects, got {c['total']}"
        assert c["status"] == "active"
        assert c["daily_limit"] == 25
        assert "{name}" in c["message_template"] and "{brand}" in c["message_template"]
        # counters consistent
        assert c["sent"] + c["failed"] + c["pending"] <= c["total"]

    def test_no_mongo_object_id_leak(self, client):
        r = client.get(f"{BASE_URL}/api/campaigns", timeout=60)
        for c in r.json()["campaigns"]:
            assert "_id" not in c.keys()

    def test_excel_source_file_deployed(self):
        p = Path("/app/backend/uploads/prospects.xlsx")
        assert p.exists(), "prospects.xlsx not deployed with code"
        assert p.stat().st_size > 0


# ---- Prospects ----
class TestProspects:
    def test_get_prospects(self, client):
        r = client.get(f"{BASE_URL}/api/campaigns/{CID}/prospects", timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["total"] >= 76
        prospects = data["prospects"]
        assert len(prospects) > 0
        p = prospects[0]
        for key in ["name", "brand", "linkedin_url", "public_id", "status", "rank"]:
            assert key in p, f"missing {key}"
        assert "_id" not in p
        # data quality across returned page
        assert all(x["name"] for x in prospects), "some prospects have empty name"
        assert all(x["brand"] for x in prospects), "some prospects have empty brand"
        assert all("linkedin.com" in x["linkedin_url"] for x in prospects)
        # sorted by rank ascending
        ranks = [x["rank"] for x in prospects]
        assert ranks == sorted(ranks)

    def test_prospects_pagination(self, client):
        r = client.get(f"{BASE_URL}/api/campaigns/{CID}/prospects?limit=5&skip=0", timeout=60)
        assert r.status_code == 200
        first = r.json()["prospects"]
        assert len(first) == 5
        r2 = client.get(f"{BASE_URL}/api/campaigns/{CID}/prospects?limit=5&skip=5", timeout=60)
        second = r2.json()["prospects"]
        assert len(second) == 5
        assert {p["public_id"] for p in first}.isdisjoint({p["public_id"] for p in second})

    def test_prospects_status_filter(self, client):
        r = client.get(f"{BASE_URL}/api/campaigns/{CID}/prospects?status=pending", timeout=60)
        assert r.status_code == 200
        assert all(p["status"] == "pending" for p in r.json()["prospects"])

    def test_prospects_unknown_campaign_returns_empty(self, client):
        r = client.get(f"{BASE_URL}/api/campaigns/TEST_nope/prospects", timeout=60)
        assert r.status_code == 200
        assert r.json()["total"] == 0


# ---- Retry failed ----
class TestRetryFailed:
    def test_retry_failed_resets_to_pending(self, client):
        before = client.get(f"{BASE_URL}/api/campaigns", timeout=60).json()["campaigns"]
        c_before = next(c for c in before if c["campaign_id"] == CID)
        failed_before = c_before["failed"]

        r = client.post(f"{BASE_URL}/api/campaigns/{CID}/retry-failed", timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["success"] is True
        assert body["reset"] == failed_before

        after = client.get(f"{BASE_URL}/api/campaigns", timeout=60).json()["campaigns"]
        c_after = next(c for c in after if c["campaign_id"] == CID)
        assert c_after["failed"] == 0
        assert c_after["pending"] == c_before["pending"] + failed_before
        # no failed prospects remain
        fr = client.get(f"{BASE_URL}/api/campaigns/{CID}/prospects?status=failed", timeout=60)
        assert fr.json()["total"] == 0

    def test_retry_failed_idempotent(self, client):
        r = client.post(f"{BASE_URL}/api/campaigns/{CID}/retry-failed", timeout=60)
        assert r.status_code == 200
        assert r.json()["reset"] == 0


# ---- Seed idempotency (direct import) ----
class TestSeedIdempotency:
    def test_seed_is_idempotent(self, client):
        import sys
        import asyncio
        sys.path.insert(0, "/app/backend")
        for k, v in dotenv_values("/app/backend/.env").items():
            if v is not None:
                os.environ.setdefault(k, v)
        from routes.campaign_manager import seed_myntra_campaign

        before = client.get(f"{BASE_URL}/api/campaigns/{CID}/prospects", timeout=60).json()["total"]
        asyncio.run(seed_myntra_campaign())
        after = client.get(f"{BASE_URL}/api/campaigns/{CID}/prospects", timeout=60).json()["total"]
        assert after == before, "re-running seed duplicated data"
