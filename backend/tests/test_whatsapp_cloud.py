"""
Tests for:
 - Campaign cloud assets (Emergent Object Storage) endpoints
 - Qikchat WhatsApp integration endpoints
Run: cd /app/backend && python -m pytest tests/test_whatsapp_cloud.py -v
"""
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
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ============== Cloud assets ==============
class TestCloudAssets:
    def test_cloud_assets_status(self, api):
        r = api.get(f"{BASE_URL}/api/campaigns/cloud-assets/status", timeout=90)
        assert r.status_code == 200, r.text[:500]
        data = r.json()
        assert set(data.keys()) == {"brochure", "prospects"}
        assert data["brochure"] is True, f"brochure missing in cloud storage: {data}"
        assert data["prospects"] is True, f"prospects missing in cloud storage: {data}"

    def test_cloud_assets_upload(self, api):
        r = api.post(f"{BASE_URL}/api/campaigns/cloud-assets/upload", json={}, timeout=180)
        assert r.status_code == 200, r.text[:500]
        data = r.json()
        assert data.get("success") is True
        assert isinstance(data.get("detail"), str) and data["detail"]

    def test_status_after_upload_still_true(self, api):
        r = api.get(f"{BASE_URL}/api/campaigns/cloud-assets/status", timeout=90)
        assert r.status_code == 200
        assert r.json() == {"brochure": True, "prospects": True}


# ============== Campaigns ==============
class TestCampaigns:
    def test_list_campaigns_has_myntra(self, api):
        r = api.get(f"{BASE_URL}/api/campaigns", timeout=60)
        assert r.status_code == 200, r.text[:500]
        campaigns = r.json()["campaigns"]
        assert isinstance(campaigns, list) and campaigns
        myntra = next((c for c in campaigns if c["campaign_id"] == "7701ea79"), None)
        assert myntra is not None, "Myntra campaign 7701ea79 not seeded"
        assert "Myntra 500" in myntra["name"]
        for k in ["total", "sent", "failed", "pending"]:
            assert isinstance(myntra[k], int)
        assert myntra["total"] > 0
        assert myntra["total"] == myntra["sent"] + myntra["failed"] + myntra["pending"]
        assert myntra.get("attachment_cloud_path") == "vnagents-crm/campaigns/fundle_marketplace_brochure.pdf"
        assert "_id" not in myntra

    def test_myntra_prospects(self, api):
        r = api.get(f"{BASE_URL}/api/campaigns/7701ea79/prospects", timeout=60)
        assert r.status_code == 200, r.text[:500]
        data = r.json()
        assert data["total"] > 0
        prospects = data["prospects"]
        assert prospects
        p = prospects[0]
        for k in ["campaign_id", "name", "brand", "linkedin_url", "public_id", "status"]:
            assert k in p, f"missing {k} in prospect"
        assert "_id" not in p
        assert p["campaign_id"] == "7701ea79"


# ============== WhatsApp ==============
class TestWhatsAppConfig:
    def test_config_configured(self, api):
        r = api.get(f"{BASE_URL}/api/whatsapp/config", timeout=30)
        assert r.status_code == 200, r.text[:500]
        data = r.json()
        assert data["configured"] is True, f"QIKCHAT_API_KEY not loaded: {data}"
        assert data["api_key_set"] is True

    def test_config_update_requires_key(self, api):
        r = api.post(f"{BASE_URL}/api/whatsapp/config", json={"api_key": ""}, timeout=30)
        assert r.status_code == 400, r.text[:500]
        assert "required" in r.json()["detail"].lower()


class TestWhatsAppStats:
    def test_stats(self, api):
        r = api.get(f"{BASE_URL}/api/whatsapp/stats", timeout=30)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert set(d.keys()) == {"total", "sent", "failed"}
        for k in d:
            assert isinstance(d[k], int) and d[k] >= 0
        assert d["sent"] + d["failed"] <= d["total"]

    def test_messages_history(self, api):
        r = api.get(f"{BASE_URL}/api/whatsapp/messages?limit=5", timeout=30)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert isinstance(d["messages"], list)
        assert isinstance(d["total"], int)
        assert len(d["messages"]) <= 5
        for m in d["messages"]:
            assert "_id" not in m
            assert "phone" in m and "status" in m


class TestWhatsAppSendValidation:
    """Validation-only: no real messages are sent to real numbers."""

    def test_send_missing_phone(self, api):
        r = api.post(f"{BASE_URL}/api/whatsapp/send", json={"message": "hi"}, timeout=30)
        assert r.status_code == 400, r.text[:500]
        assert "phone" in r.json()["detail"].lower()

    def test_send_missing_message(self, api):
        r = api.post(f"{BASE_URL}/api/whatsapp/send", json={"phone": "+919999999999"}, timeout=30)
        assert r.status_code == 400, r.text[:500]
        assert "message" in r.json()["detail"].lower()

    def test_send_empty_body(self, api):
        r = api.post(f"{BASE_URL}/api/whatsapp/send", json={}, timeout=30)
        assert r.status_code == 400, r.text[:500]

    def test_send_bulk_no_contacts(self, api):
        r = api.post(f"{BASE_URL}/api/whatsapp/send-bulk", json={"message": "hi"}, timeout=30)
        assert r.status_code == 400
        assert "contact" in r.json()["detail"].lower()

    def test_send_bulk_no_message(self, api):
        r = api.post(
            f"{BASE_URL}/api/whatsapp/send-bulk",
            json={"contacts": [{"phone": "9999999999", "name": "TEST"}]},
            timeout=30,
        )
        assert r.status_code == 400
        assert "message" in r.json()["detail"].lower()

    def test_send_invalid_number_is_handled_gracefully(self, api):
        """Send to a clearly invalid number: must not 500; should return success=False."""
        r = api.post(
            f"{BASE_URL}/api/whatsapp/send",
            json={"phone": "+910000000000", "message": "TEST_validation", "contact_name": "TEST_QA"},
            timeout=60,
        )
        assert r.status_code == 200, f"unexpected status {r.status_code}: {r.text[:500]}"
        d = r.json()
        assert "success" in d
        assert "detail" in d
