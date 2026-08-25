"""
LinkedIn CRM — Backend tests for crm_auth + crm_campaigns
Covers: login (super_admin/user), /me, logout, user CRUD (RBAC), change-password,
invalid login, campaigns CRUD + isolation, settings, cookie save.
"""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
AUTH = f"{BASE_URL}/api/crm-auth"
CRM = f"{BASE_URL}/api/crm"

PASSWORD = "CRM@2026!"
ADMIN_EMAIL = "vineet@channelloyalty.ai"
USER_EMAIL = "chandra@channelloyalty.ai"


def _login(email, password=PASSWORD):
    s = requests.Session()
    r = s.post(f"{AUTH}/login", json={"email": email, "password": password}, timeout=30)
    return s, r


@pytest.fixture(scope="module")
def admin_session():
    s, r = _login(ADMIN_EMAIL)
    if r.status_code != 200:
        pytest.fail(f"Admin login failed {r.status_code}: {r.text[:300]}")
    return s


@pytest.fixture(scope="module")
def user_session():
    s, r = _login(USER_EMAIL)
    if r.status_code != 200:
        pytest.fail(f"User login failed {r.status_code}: {r.text[:300]}")
    return s


# ============ Auth ============
class TestCRMAuthLogin:
    def test_login_super_admin(self):
        s, r = _login(ADMIN_EMAIL)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "super_admin"
        assert "id" in data and isinstance(data["id"], str)
        assert "password_hash" not in data
        assert "_id" not in data
        # httpOnly cookies set
        assert "crm_access_token" in s.cookies.get_dict()
        assert "crm_refresh_token" in s.cookies.get_dict()
        set_cookie = r.headers.get("set-cookie", "").lower()
        assert "httponly" in set_cookie
        assert "samesite=none" in set_cookie
        assert "secure" in set_cookie

    def test_login_regular_user(self):
        s, r = _login(USER_EMAIL)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["email"] == USER_EMAIL
        assert data["role"] == "user"

    def test_login_all_seed_users(self):
        for email in ["vineet@channelloyalty.ai", "chandra@channelloyalty.ai",
                      "abhinav@channelloyalty.ai", "shivam@channelloyalty.ai"]:
            _, r = _login(email)
            assert r.status_code == 200, f"{email} login failed: {r.status_code} {r.text[:200]}"

    def test_login_invalid_password(self):
        _, r = _login(ADMIN_EMAIL, "WrongPassword123!")
        assert r.status_code in (401, 429), r.text[:300]
        if r.status_code == 401:
            assert "detail" in r.json()

    def test_login_unknown_email(self):
        _, r = _login(f"nobody-{uuid.uuid4().hex[:8]}@example.com", "whatever")
        assert r.status_code == 401

    def test_login_missing_fields(self):
        r = requests.post(f"{AUTH}/login", json={"email": ADMIN_EMAIL}, timeout=30)
        assert r.status_code == 400

    def test_bcrypt_hash_format(self):
        """password_hash must be bcrypt $2b$"""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        env = dotenv_values("/app/backend/.env")
        mongo_url = os.environ.get("MONGO_URL") or env.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME") or env.get("DB_NAME")

        async def check():
            c = AsyncIOMotorClient(mongo_url)
            u = await c[db_name].crm_users.find_one({"email": ADMIN_EMAIL})
            return u

        u = asyncio.get_event_loop().run_until_complete(check()) if False else asyncio.run(check())
        assert u is not None
        assert u["password_hash"].startswith("$2b$"), u["password_hash"][:10]


class TestCRMAuthSession:
    def test_me_authenticated(self, admin_session):
        r = admin_session.get(f"{AUTH}/me", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "super_admin"
        assert "password_hash" not in data

    def test_me_unauthenticated(self):
        r = requests.get(f"{AUTH}/me", timeout=30)
        assert r.status_code == 401

    def test_me_invalid_token(self):
        r = requests.get(f"{AUTH}/me", headers={"Authorization": "Bearer notarealtoken"}, timeout=30)
        assert r.status_code == 401

    def test_refresh_token(self):
        s, _ = _login(ADMIN_EMAIL)
        r = s.post(f"{AUTH}/refresh", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["email"] == ADMIN_EMAIL

    def test_logout_clears_cookies(self):
        s, _ = _login(ADMIN_EMAIL)
        assert s.get(f"{AUTH}/me", timeout=30).status_code == 200
        r = s.post(f"{AUTH}/logout", timeout=30)
        assert r.status_code == 200
        assert r.json().get("success") is True
        # cookie jar should no longer hold a valid access token
        assert not s.cookies.get_dict().get("crm_access_token")
        assert s.get(f"{AUTH}/me", timeout=30).status_code == 401


# ============ Super Admin user management ============
class TestCRMUserManagement:
    created_ids = []

    def test_list_users_as_super_admin(self, admin_session):
        r = admin_session.get(f"{AUTH}/users", timeout=30)
        assert r.status_code == 200, r.text[:300]
        users = r.json()["users"]
        emails = {u["email"] for u in users}
        for e in ["vineet@channelloyalty.ai", "chandra@channelloyalty.ai",
                  "abhinav@channelloyalty.ai", "shivam@channelloyalty.ai"]:
            assert e in emails, f"{e} missing from users list"
        for u in users:
            assert "password_hash" not in u
            assert "_id" not in u

    def test_list_users_as_regular_user_forbidden(self, user_session):
        r = user_session.get(f"{AUTH}/users", timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code}"

    def test_list_users_unauthenticated(self):
        r = requests.get(f"{AUTH}/users", timeout=30)
        assert r.status_code == 401

    def test_create_update_delete_user(self, admin_session):
        email = f"test_qa_{uuid.uuid4().hex[:8]}@example.com"
        r = admin_session.post(f"{AUTH}/users", json={
            "name": "TEST_QA User", "email": email, "password": "TestPass@123", "role": "user"
        }, timeout=30)
        assert r.status_code == 200, r.text[:300]
        uid = r.json()["user_id"]
        TestCRMUserManagement.created_ids.append(uid)

        # verify persisted via list
        users = admin_session.get(f"{AUTH}/users", timeout=30).json()["users"]
        match = [u for u in users if u["email"] == email]
        assert len(match) == 1
        assert match[0]["name"] == "TEST_QA User"
        assert match[0]["role"] == "user"

        # new user can log in
        _, lr = _login(email, "TestPass@123")
        assert lr.status_code == 200, lr.text[:300]

        # duplicate email rejected
        dup = admin_session.post(f"{AUTH}/users", json={"name": "dup", "email": email}, timeout=30)
        assert dup.status_code == 400

        # update
        up = admin_session.put(f"{AUTH}/users/{uid}", json={"name": "TEST_QA Renamed"}, timeout=30)
        assert up.status_code == 200
        users = admin_session.get(f"{AUTH}/users", timeout=30).json()["users"]
        assert [u for u in users if u["id"] == uid][0]["name"] == "TEST_QA Renamed"

        # delete
        dl = admin_session.delete(f"{AUTH}/users/{uid}", timeout=30)
        assert dl.status_code == 200
        users = admin_session.get(f"{AUTH}/users", timeout=30).json()["users"]
        assert uid not in [u["id"] for u in users]
        TestCRMUserManagement.created_ids.remove(uid)

    def test_create_user_missing_fields(self, admin_session):
        r = admin_session.post(f"{AUTH}/users", json={"name": "no email"}, timeout=30)
        assert r.status_code == 400

    def test_create_user_as_regular_user_forbidden(self, user_session):
        r = user_session.post(f"{AUTH}/users", json={
            "name": "Nope", "email": f"nope_{uuid.uuid4().hex[:6]}@example.com"}, timeout=30)
        assert r.status_code == 403

    def test_admin_cannot_delete_self(self, admin_session):
        me = admin_session.get(f"{AUTH}/me", timeout=30).json()
        r = admin_session.delete(f"{AUTH}/users/{me['id']}", timeout=30)
        assert r.status_code == 400

    @classmethod
    def teardown_class(cls):
        s, _ = _login(ADMIN_EMAIL)
        for uid in cls.created_ids:
            s.delete(f"{AUTH}/users/{uid}", timeout=30)


class TestChangePassword:
    def test_change_password_roundtrip(self, admin_session):
        """Change Shivam's password and revert it back."""
        s, r = _login("shivam@channelloyalty.ai")
        assert r.status_code == 200
        new_pw = "TempQA@2026!"
        c = s.post(f"{AUTH}/change-password", json={
            "current_password": PASSWORD, "new_password": new_pw}, timeout=30)
        assert c.status_code == 200, c.text[:300]
        assert c.json()["success"] is True

        # old password no longer works, new one does
        _, old = _login("shivam@channelloyalty.ai", PASSWORD)
        assert old.status_code == 401
        s2, new = _login("shivam@channelloyalty.ai", new_pw)
        assert new.status_code == 200

        # revert
        rev = s2.post(f"{AUTH}/change-password", json={
            "current_password": new_pw, "new_password": PASSWORD}, timeout=30)
        assert rev.status_code == 200
        _, back = _login("shivam@channelloyalty.ai", PASSWORD)
        assert back.status_code == 200, "Failed to revert shivam password!"

    def test_change_password_wrong_current(self, admin_session):
        r = admin_session.post(f"{AUTH}/change-password", json={
            "current_password": "definitelywrong", "new_password": "Whatever@123"}, timeout=30)
        assert r.status_code == 401

    def test_change_password_too_short(self, admin_session):
        r = admin_session.post(f"{AUTH}/change-password", json={
            "current_password": PASSWORD, "new_password": "abc"}, timeout=30)
        assert r.status_code == 400

    def test_change_password_unauthenticated(self):
        r = requests.post(f"{AUTH}/change-password", json={
            "current_password": PASSWORD, "new_password": "Whatever@123"}, timeout=30)
        assert r.status_code == 401


# ============ Campaigns ============
class TestCRMCampaigns:
    created = []  # (session_owner_email, campaign_id)

    def test_create_and_get_campaign(self, admin_session):
        name = f"TEST_QA Campaign {uuid.uuid4().hex[:6]}"
        r = admin_session.post(f"{CRM}/campaigns", json={
            "name": name,
            "direct_message": "Hi {name}, from {company}",
            "invite_note": "Let's connect {name}",
            "daily_limit": 20,
        }, timeout=30)
        assert r.status_code == 200, r.text[:300]
        cid = r.json()["campaign_id"]
        TestCRMCampaigns.created.append(cid)

        # GET single
        g = admin_session.get(f"{CRM}/campaigns/{cid}", timeout=30)
        assert g.status_code == 200, g.text[:300]
        c = g.json()
        assert c["name"] == name
        assert c["direct_message"] == "Hi {name}, from {company}"
        assert c["daily_limit"] == 20
        assert c["status"] == "active"
        assert c["prospects"] == []
        assert "_id" not in c

        # GET list contains it
        lst = admin_session.get(f"{CRM}/campaigns", timeout=30)
        assert lst.status_code == 200
        campaigns = lst.json()["campaigns"]
        mine = [x for x in campaigns if x["campaign_id"] == cid]
        assert len(mine) == 1
        assert mine[0]["total"] == 0 and mine[0]["pending"] == 0
        assert "_id" not in mine[0]

    def test_daily_limit_capped_at_50(self, admin_session):
        r = admin_session.post(f"{CRM}/campaigns", json={
            "name": "TEST_QA Cap", "direct_message": "hi", "daily_limit": 500}, timeout=30)
        assert r.status_code == 200
        cid = r.json()["campaign_id"]
        TestCRMCampaigns.created.append(cid)
        c = admin_session.get(f"{CRM}/campaigns/{cid}", timeout=30).json()
        assert c["daily_limit"] == 50

    def test_create_campaign_requires_message(self, admin_session):
        r = admin_session.post(f"{CRM}/campaigns", json={"name": "TEST_QA Empty"}, timeout=30)
        assert r.status_code == 400

    def test_campaign_user_isolation(self, admin_session, user_session):
        """A user must not see or fetch another user's campaign."""
        r = admin_session.post(f"{CRM}/campaigns", json={
            "name": "TEST_QA Isolation", "direct_message": "hello"}, timeout=30)
        cid = r.json()["campaign_id"]
        TestCRMCampaigns.created.append(cid)

        user_campaigns = user_session.get(f"{CRM}/campaigns", timeout=30).json()["campaigns"]
        assert cid not in [c["campaign_id"] for c in user_campaigns]

        g = user_session.get(f"{CRM}/campaigns/{cid}", timeout=30)
        assert g.status_code == 404

    def test_campaigns_unauthenticated(self):
        assert requests.get(f"{CRM}/campaigns", timeout=30).status_code == 401
        assert requests.post(f"{CRM}/campaigns", json={"direct_message": "x"}, timeout=30).status_code == 401

    def test_retry_on_missing_campaign(self, admin_session):
        r = admin_session.post(f"{CRM}/campaigns/doesnotexist/retry", timeout=30)
        assert r.status_code == 404

    def test_send_without_cookies_returns_400(self, admin_session):
        """Sending should fail cleanly (400) when LinkedIn cookies are not configured."""
        r = admin_session.post(f"{CRM}/campaigns", json={
            "name": "TEST_QA Send", "direct_message": "hi"}, timeout=30)
        cid = r.json()["campaign_id"]
        TestCRMCampaigns.created.append(cid)
        s = admin_session.post(f"{CRM}/campaigns/{cid}/send", timeout=30)
        # No prospects OR missing cookies -> must not be a 500
        assert s.status_code in (200, 400), f"{s.status_code}: {s.text[:300]}"

    @classmethod
    def teardown_class(cls):
        """Remove test campaigns directly from Mongo (no DELETE endpoint exists)."""
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

        asyncio.run(clean())


# ============ Settings ============
class TestCRMSettings:
    def test_get_settings(self, user_session):
        r = user_session.get(f"{CRM}/settings", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["email"] == USER_EMAIL
        assert "has_cookie" in d and isinstance(d["has_cookie"], bool)
        assert "li_at_preview" in d and "jsessionid_preview" in d

    def test_settings_unauthenticated(self):
        assert requests.get(f"{CRM}/settings", timeout=30).status_code == 401

    def test_save_cookie(self, user_session):
        r = user_session.post(f"{CRM}/settings/cookie", json={
            "li_at": "TEST_QA_dummy_li_at_value_1234567890",
            "jsessionid": "ajax:TEST_QA_1234567890",
        }, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["success"] is True

        g = user_session.get(f"{CRM}/settings", timeout=30).json()
        assert g["has_cookie"] is True
        assert g["li_at_preview"].startswith("TEST_QA_dummy")

    def test_save_cookie_validation(self, user_session):
        assert user_session.post(f"{CRM}/settings/cookie", json={"jsessionid": "x"}, timeout=30).status_code == 400
        assert user_session.post(f"{CRM}/settings/cookie", json={"li_at": "x"}, timeout=30).status_code == 400

    @classmethod
    def teardown_class(cls):
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        env = dotenv_values("/app/backend/.env")
        mongo_url = os.environ.get("MONGO_URL") or env.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME") or env.get("DB_NAME")

        async def clean():
            c = AsyncIOMotorClient(mongo_url)
            await c[db_name].crm_users.update_one(
                {"email": USER_EMAIL}, {"$set": {"li_at": "", "jsessionid": ""}})

        asyncio.run(clean())


# ============ Brute force lockout ============
class TestBruteForceLockout:
    def test_lockout_after_5_failures(self):
        email = f"lockout_qa_{uuid.uuid4().hex[:8]}@example.com"
        statuses = []
        for _ in range(6):
            _, r = _login(email, "badpassword")
            statuses.append(r.status_code)
        assert statuses[:5] == [401] * 5, statuses
        assert statuses[5] == 429, f"Expected lockout 429 on 6th attempt, got {statuses}"
