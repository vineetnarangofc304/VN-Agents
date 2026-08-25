"""LinkedIn CRM — XLSX prospect upload tests (no LinkedIn API calls)."""
import io
import os
import uuid

import openpyxl
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
AUTH = f"{BASE_URL}/api/crm-auth"
CRM = f"{BASE_URL}/api/crm"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{AUTH}/login", json={"email": "vineet@channelloyalty.ai", "password": "CRM@2026!"}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:200]}")
    return s


def _xlsx(rows, headers=("Contact Name", "Company", "Title", "LinkedIn")):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class TestProspectUpload:
    created = []

    def _new_campaign(self, s):
        r = s.post(f"{CRM}/campaigns", json={"name": f"TEST_QA Upload {uuid.uuid4().hex[:6]}",
                                             "direct_message": "hi {name}"}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        cid = r.json()["campaign_id"]
        TestProspectUpload.created.append(cid)
        return cid

    def test_upload_valid_xlsx(self, admin_session):
        cid = self._new_campaign(admin_session)
        buf = _xlsx([
            ("QA One", "Acme", "CEO", "https://www.linkedin.com/in/qa-one-testqa/"),
            ("QA Two", "Beta", "CTO", "https://linkedin.com/in/qa-two-testqa"),
            ("Bad Row", "Gamma", "VP", "not-a-url"),
        ])
        r = admin_session.post(f"{CRM}/campaigns/{cid}/upload",
                               files={"file": ("prospects.xlsx", buf,
                                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                               timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["imported"] == 2, r.json()

        # verify persistence + parsing
        c = admin_session.get(f"{CRM}/campaigns/{cid}", timeout=30).json()
        assert len(c["prospects"]) == 2
        p = c["prospects"][0]
        assert p["name"] == "QA One"
        assert p["company"] == "Acme"
        assert p["title"] == "CEO"
        assert p["public_id"] == "qa-one-testqa"
        assert p["status"] == "pending"
        assert "_id" not in p

        # stats reflected in list
        lst = admin_session.get(f"{CRM}/campaigns", timeout=30).json()["campaigns"]
        mine = [x for x in lst if x["campaign_id"] == cid][0]
        assert mine["total"] == 2 and mine["pending"] == 2

    def test_upload_dedupes_on_reupload(self, admin_session):
        cid = self._new_campaign(admin_session)
        rows = [("QA Dup", "Acme", "CEO", "https://www.linkedin.com/in/qa-dup-testqa/")]
        for expected in (1, 0):
            r = admin_session.post(f"{CRM}/campaigns/{cid}/upload",
                                   files={"file": ("p.xlsx", _xlsx(rows), "application/vnd.ms-excel")},
                                   timeout=60)
            assert r.status_code == 200, r.text[:200]
            assert r.json()["imported"] == expected

    def test_upload_missing_linkedin_column(self, admin_session):
        cid = self._new_campaign(admin_session)
        buf = _xlsx([("QA X", "Acme")], headers=("Contact Name", "Company"))
        r = admin_session.post(f"{CRM}/campaigns/{cid}/upload",
                               files={"file": ("p.xlsx", buf, "application/vnd.ms-excel")}, timeout=60)
        assert r.status_code == 400, f"{r.status_code}: {r.text[:200]}"

    def test_upload_non_xlsx_file(self, admin_session):
        cid = self._new_campaign(admin_session)
        r = admin_session.post(f"{CRM}/campaigns/{cid}/upload",
                               files={"file": ("bad.txt", io.BytesIO(b"not an excel file"), "text/plain")},
                               timeout=60)
        assert r.status_code in (400, 422), f"Expected 4xx for invalid file, got {r.status_code}: {r.text[:200]}"

    def test_upload_to_foreign_campaign_404(self, admin_session):
        cid = self._new_campaign(admin_session)
        u = requests.Session()
        u.post(f"{AUTH}/login", json={"email": "chandra@channelloyalty.ai", "password": "CRM@2026!"}, timeout=30)
        r = u.post(f"{CRM}/campaigns/{cid}/upload",
                   files={"file": ("p.xlsx", _xlsx([("a", "b", "c", "https://linkedin.com/in/x-testqa")]),
                                   "application/vnd.ms-excel")}, timeout=60)
        assert r.status_code == 404

    def test_retry_resets_failed(self, admin_session):
        cid = self._new_campaign(admin_session)
        r = admin_session.post(f"{CRM}/campaigns/{cid}/retry", timeout=30)
        assert r.status_code == 200
        assert r.json()["reset"] == 0

    @classmethod
    def teardown_class(cls):
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        env = dotenv_values("/app/backend/.env")
        mongo_url = os.environ.get("MONGO_URL") or env.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME") or env.get("DB_NAME")

        async def clean():
            c = AsyncIOMotorClient(mongo_url)
            db = c[db_name]
            for cid in cls.created:
                await db.crm_campaigns.delete_many({"campaign_id": cid})
                await db.crm_prospects.delete_many({"campaign_id": cid})
            # remove UI-created test campaigns too
            async for camp in db.crm_campaigns.find({"name": {"$regex": "TEST_QA"}}):
                await db.crm_prospects.delete_many({"campaign_id": camp["campaign_id"]})
                await db.crm_campaigns.delete_one({"_id": camp["_id"]})

        asyncio.run(clean())
