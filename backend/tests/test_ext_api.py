"""
LinkedLeads.ai — Extension API + CRM Auth tests
Covers: /api/crm-auth/* (login, me, users) and /api/ext/* (stats, campaigns, tasks, upload, download)
"""
import io
import os
import zipfile

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

ADMIN_EMAIL = "vineet@channelloyalty.ai"
ADMIN_PASSWORD = "CRM@2026!"
USER_EMAIL = "chandra@channelloyalty.ai"


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/crm-auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Admin login failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="session")
def created_campaigns():
    return []


@pytest.fixture(scope="session", autouse=True)
def cleanup(admin_session, created_campaigns):
    yield
    for cid in created_campaigns:
        admin_session.delete(f"{BASE_URL}/api/ext/campaigns/{cid}", timeout=30)


# ============ CRM Auth ============
class TestCRMAuth:
    def test_login_success_sets_cookie_and_token(self):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/crm-auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["email"] == ADMIN_EMAIL
        assert d["role"] == "super_admin"
        assert isinstance(d.get("token"), str) and len(d["token"]) > 20
        assert "password_hash" not in d
        assert "li_at" not in d
        assert "crm_access_token" in s.cookies.get_dict()
        # httpOnly check on raw header
        set_cookie = r.headers.get("set-cookie", "")
        assert "httponly" in set_cookie.lower()

    def test_login_second_user(self):
        r = requests.post(f"{BASE_URL}/api/crm-auth/login", json={"email": USER_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["role"] == "user"

    def test_login_invalid_password(self):
        r = requests.post(f"{BASE_URL}/api/crm-auth/login", json={"email": ADMIN_EMAIL, "password": "WrongPass123"}, timeout=30)
        assert r.status_code == 401
        assert "detail" in r.json()

    def test_login_missing_fields(self):
        r = requests.post(f"{BASE_URL}/api/crm-auth/login", json={"email": "", "password": ""}, timeout=30)
        assert r.status_code == 400

    def test_me_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/crm-auth/me", timeout=30)
        assert r.status_code == 401

    def test_me_authenticated(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/crm-auth/me", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == ADMIN_EMAIL
        assert "has_cookie" in d
        assert "_id" not in d

    def test_bcrypt_hash_format(self):
        # Verify stored hash format via direct DB check
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL") or dotenv_values("/app/backend/.env").get("MONGO_URL")
        db_name = os.environ.get("DB_NAME") or dotenv_values("/app/backend/.env").get("DB_NAME")
        c = MongoClient(mongo_url)
        u = c[db_name].crm_users.find_one({"email": ADMIN_EMAIL})
        assert u is not None
        assert u["password_hash"].startswith("$2b$"), u["password_hash"][:10]
        c.close()

    def test_list_users_super_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/crm-auth/users", timeout=30)
        assert r.status_code == 200
        users = r.json()["users"]
        assert len(users) >= 2
        emails = [u["email"] for u in users]
        assert ADMIN_EMAIL in emails
        for u in users:
            assert "password_hash" not in u
            assert "_id" not in u

    def test_list_users_forbidden_for_regular_user(self):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/crm-auth/login", json={"email": USER_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
        s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
        r2 = s.get(f"{BASE_URL}/api/crm-auth/users", timeout=30)
        assert r2.status_code == 403

    def test_logout(self, ):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/crm-auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
        r = s.post(f"{BASE_URL}/api/crm-auth/logout", timeout=30)
        assert r.status_code == 200
        assert r.json()["success"] is True
        r2 = s.get(f"{BASE_URL}/api/crm-auth/me", timeout=30)
        assert r2.status_code == 401

    def test_update_cookies_endpoint_used_by_settings_ui(self, admin_session):
        """SettingsView posts to /api/crm-auth/update-cookies — verify it exists."""
        r = admin_session.post(f"{BASE_URL}/api/crm-auth/update-cookies",
                               json={"li_at": "TEST_dummy", "jsessionid": "ajax:123"}, timeout=30)
        assert r.status_code in (200, 201), f"Settings save-cookies endpoint returned {r.status_code}: {r.text[:200]}"


# ============ Ext Stats ============
class TestExtStats:
    def test_stats_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/ext/stats", timeout=30)
        assert r.status_code == 401

    def test_stats_shape(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/ext/stats", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ("connects", "messages", "visits"):
            assert isinstance(d["today"][k], int)
        assert isinstance(d["active_campaigns"], int)
        assert isinstance(d["pending_tasks"], int)
        assert isinstance(d["total_completed"], int)


# ============ Ext Session ============
class TestExtSession:
    def test_report_session(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/ext/session", json={"active": True, "li_at_prefix": "AQED"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["ok"] is True


# ============ Campaigns CRUD ============
class TestExtCampaigns:
    def test_list_campaigns(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/ext/campaigns", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json()["campaigns"], list)
        for c in r.json()["campaigns"]:
            assert "_id" not in c

    def test_create_campaign_and_verify_persistence(self, admin_session, created_campaigns):
        payload = {
            "name": "TEST_Campaign_Alpha",
            "type": "connect",
            "message_template": "Hi {{first_name}}",
            "daily_limit": 15,
            "prospects": [
                {"profile_url": "https://www.linkedin.com/in/test-prospect-1/", "name": "TEST P1", "company": "Acme", "title": "CTO"},
                {"profile_url": "https://www.linkedin.com/in/test-prospect-2/", "name": "TEST P2", "company": "Globex", "title": "VP"},
            ],
        }
        r = admin_session.post(f"{BASE_URL}/api/ext/campaigns", json=payload, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        cid = d["campaign_id"]
        created_campaigns.append(cid)
        assert d["tasks_created"] == 2
        assert d["status"] == "active"

        # GET verify persistence
        lst = admin_session.get(f"{BASE_URL}/api/ext/campaigns", timeout=30).json()["campaigns"]
        found = next((c for c in lst if c["campaign_id"] == cid), None)
        assert found is not None
        assert found["name"] == "TEST_Campaign_Alpha"
        assert found["type"] == "connect"
        assert found["total_prospects"] == 2
        assert found["daily_limit"] == 15
        assert found["status"] == "active"

    def test_campaign_tasks_public_id_extraction(self, admin_session, created_campaigns):
        cid = created_campaigns[0]
        r = admin_session.get(f"{BASE_URL}/api/ext/campaigns/{cid}/tasks", timeout=30)
        assert r.status_code == 200
        tasks = r.json()["tasks"]
        assert r.json()["total"] == 2
        ids = sorted(t["target_public_id"] for t in tasks)
        assert ids == ["test-prospect-1", "test-prospect-2"]
        assert all(t["status"] == "pending" for t in tasks)
        assert tasks[0]["prospect"]["company"] in ("Acme", "Globex")

    def test_pause_and_resume(self, admin_session, created_campaigns):
        cid = created_campaigns[0]
        assert admin_session.post(f"{BASE_URL}/api/ext/campaigns/{cid}/pause", timeout=30).status_code == 200
        lst = admin_session.get(f"{BASE_URL}/api/ext/campaigns", timeout=30).json()["campaigns"]
        c = next(x for x in lst if x["campaign_id"] == cid)
        assert c["status"] == "paused"
        tasks = admin_session.get(f"{BASE_URL}/api/ext/campaigns/{cid}/tasks", timeout=30).json()["tasks"]
        assert all(t["status"] == "paused" for t in tasks)

        assert admin_session.post(f"{BASE_URL}/api/ext/campaigns/{cid}/resume", timeout=30).status_code == 200
        lst = admin_session.get(f"{BASE_URL}/api/ext/campaigns", timeout=30).json()["campaigns"]
        c = next(x for x in lst if x["campaign_id"] == cid)
        assert c["status"] == "active"
        tasks = admin_session.get(f"{BASE_URL}/api/ext/campaigns/{cid}/tasks", timeout=30).json()["tasks"]
        assert all(t["status"] == "pending" for t in tasks)

    def test_tasks_filter_by_status(self, admin_session, created_campaigns):
        cid = created_campaigns[0]
        r = admin_session.get(f"{BASE_URL}/api/ext/campaigns/{cid}/tasks", params={"status": "completed"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_upload_prospects_xlsx(self, admin_session, created_campaigns):
        import openpyxl
        cid = created_campaigns[0]
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Profile URL", "Name", "Company", "Title", "Location"])
        ws.append(["https://www.linkedin.com/in/test-upload-1/", "TEST Upload One", "Initech", "Director", "Delhi"])
        ws.append(["https://www.linkedin.com/in/test-upload-2/", "TEST Upload Two", "Umbrella", "Manager", "Mumbai"])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        r = admin_session.post(
            f"{BASE_URL}/api/ext/campaigns/{cid}/upload-prospects",
            files={"file": ("TEST_prospects.xlsx", buf.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=60,
        )
        assert r.status_code == 200, r.text[:400]
        assert r.json()["prospects_added"] == 2

        tasks = admin_session.get(f"{BASE_URL}/api/ext/campaigns/{cid}/tasks", timeout=30).json()["tasks"]
        assert len(tasks) == 4
        names = [t["prospect"]["name"] for t in tasks]
        assert "TEST Upload One" in names
        uploaded = next(t for t in tasks if t["prospect"]["name"] == "TEST Upload One")
        assert uploaded["prospect"]["company"] == "Initech"
        assert uploaded["prospect"]["title"] == "Director"
        assert uploaded["target_public_id"] == "test-upload-1"

        lst = admin_session.get(f"{BASE_URL}/api/ext/campaigns", timeout=30).json()["campaigns"]
        c = next(x for x in lst if x["campaign_id"] == cid)
        assert c["total_prospects"] == 4

    def test_upload_to_nonexistent_campaign_404(self, admin_session):
        import openpyxl
        wb = openpyxl.Workbook()
        wb.active.append(["Profile URL", "Name"])
        buf = io.BytesIO()
        wb.save(buf)
        r = admin_session.post(
            f"{BASE_URL}/api/ext/campaigns/nope-does-not-exist/upload-prospects",
            files={"file": ("TEST_x.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=60,
        )
        assert r.status_code == 404

    def test_upload_invalid_file_returns_4xx(self, admin_session, created_campaigns):
        cid = created_campaigns[0]
        r = admin_session.post(
            f"{BASE_URL}/api/ext/campaigns/{cid}/upload-prospects",
            files={"file": ("TEST_bad.xlsx", b"this is not a spreadsheet", "application/octet-stream")},
            timeout=60,
        )
        assert r.status_code in (400, 415, 422), f"Expected 4xx for corrupt file, got {r.status_code}"

    def test_delete_campaign_removes_tasks(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/ext/campaigns", json={
            "name": "TEST_Campaign_ToDelete", "type": "visit", "prospects": [
                {"profile_url": "https://www.linkedin.com/in/test-del-1/", "name": "TEST Del"}]
        }, timeout=30)
        cid = r.json()["campaign_id"]
        assert admin_session.delete(f"{BASE_URL}/api/ext/campaigns/{cid}", timeout=30).status_code == 200
        lst = admin_session.get(f"{BASE_URL}/api/ext/campaigns", timeout=30).json()["campaigns"]
        assert all(c["campaign_id"] != cid for c in lst)
        tasks = admin_session.get(f"{BASE_URL}/api/ext/campaigns/{cid}/tasks", timeout=30).json()["tasks"]
        assert tasks == []

    def test_campaign_isolation_between_users(self, admin_session, created_campaigns):
        s = requests.Session()
        lr = s.post(f"{BASE_URL}/api/crm-auth/login", json={"email": USER_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
        s.headers.update({"Authorization": f"Bearer {lr.json()['token']}"})
        cid = created_campaigns[0]
        tasks = s.get(f"{BASE_URL}/api/ext/campaigns/{cid}/tasks", timeout=30).json()["tasks"]
        assert tasks == [], "Other user can read admin's campaign tasks"


# ============ Task Polling + Result ============
class TestExtTasks:
    def test_next_task_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/ext/tasks/next", timeout=30)
        assert r.status_code == 401

    def test_next_task_and_report_result(self, admin_session, created_campaigns):
        # Dedicated campaign
        r = admin_session.post(f"{BASE_URL}/api/ext/campaigns", json={
            "name": "TEST_Campaign_TaskFlow", "type": "visit", "message_template": "",
            "prospects": [{"profile_url": "https://www.linkedin.com/in/test-flow-1/", "name": "TEST Flow", "company": "FlowCo"}]
        }, timeout=30)
        cid = r.json()["campaign_id"]
        created_campaigns.append(cid)

        nr = admin_session.get(f"{BASE_URL}/api/ext/tasks/next", timeout=30)
        assert nr.status_code == 200, nr.text[:300]
        body = nr.json()
        if body.get("task") is None:
            pytest.fail(f"No task returned despite pending tasks: {body}")
        task = body["task"]
        assert task["task_id"]
        assert task["type"] in ("connect", "message", "visit")

        # status should now be in_progress
        tasks = admin_session.get(f"{BASE_URL}/api/ext/campaigns/{task['campaign_id']}/tasks", timeout=30).json()["tasks"]
        t = next(x for x in tasks if x["task_id"] == task["task_id"])
        assert t["status"] == "in_progress"

        # Report success
        rr = admin_session.post(f"{BASE_URL}/api/ext/tasks/{task['task_id']}/result",
                                json={"success": True, "action": task["type"], "note": "TEST ok"}, timeout=30)
        assert rr.status_code == 200, rr.text[:300]
        assert rr.json()["status"] == "completed"

        tasks = admin_session.get(f"{BASE_URL}/api/ext/campaigns/{task['campaign_id']}/tasks", timeout=30).json()["tasks"]
        t = next(x for x in tasks if x["task_id"] == task["task_id"])
        assert t["status"] == "completed"
        assert t["completed_at"] is not None

        # campaign completed_count incremented
        lst = admin_session.get(f"{BASE_URL}/api/ext/campaigns", timeout=30).json()["campaigns"]
        c = next(x for x in lst if x["campaign_id"] == task["campaign_id"])
        assert c["completed_count"] >= 1

        # stats reflect it
        stats = admin_session.get(f"{BASE_URL}/api/ext/stats", timeout=30).json()
        assert stats["total_completed"] >= 1

    def test_report_result_unknown_task_404(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/ext/tasks/507f1f77bcf86cd799439011/result",
                               json={"success": True}, timeout=30)
        assert r.status_code == 404

    def test_report_result_malformed_id_returns_4xx(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/ext/tasks/not-an-objectid/result",
                               json={"success": True}, timeout=30)
        assert r.status_code in (400, 404, 422), f"Expected 4xx for malformed id, got {r.status_code}"


# ============ Extension Download ============
class TestExtDownload:
    def test_download_returns_valid_zip(self):
        r = requests.get(f"{BASE_URL}/api/ext/download", timeout=60)
        assert r.status_code == 200, r.text[:200]
        assert "zip" in r.headers.get("content-type", "")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        assert "manifest.json" in names, names
        assert any(n.endswith("background.js") for n in names)
        assert any(n.endswith("content.js") for n in names)
        assert z.testzip() is None
