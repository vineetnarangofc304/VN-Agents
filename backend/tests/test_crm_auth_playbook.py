"""
Auth playbook verification for CRM auth (iteration 32).
Covers: bcrypt hash format, httpOnly+Secure cookies on login, CORS credentials,
brute-force lockout (throwaway email so real accounts are never locked),
seed users present.
"""
import os
import sys
import asyncio
import uuid

import pytest
import requests
from dotenv import dotenv_values

sys.path.insert(0, "/app/backend")
for _k, _v in dotenv_values("/app/backend/.env").items():
    if _v is not None:
        os.environ.setdefault(_k, _v)

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")).rstrip("/")
SUPER_ADMIN = {"email": "vineet@channelloyalty.ai", "password": "CRM@2026!"}


def _db_call(fn):
    """Run an async fn(db) with a motor client created inside a fresh loop."""
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _wrap():
        cl = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            return await fn(cl[os.environ["DB_NAME"]])
        finally:
            cl.close()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_wrap())
    finally:
        loop.close()


def _clear_attempts(email):
    _db_call(lambda db: db.crm_login_attempts.delete_one({"identifier": email}))


def _set_cookie_headers(resp):
    try:
        return resp.raw.headers.getlist("Set-Cookie")
    except Exception:
        v = resp.headers.get("Set-Cookie", "")
        return [v] if v else []


class TestAuthPlaybook:
    def test_bcrypt_hash_format(self):
        u = _db_call(lambda db: db.crm_users.find_one({"email": SUPER_ADMIN["email"]}))
        assert u, "seed super_admin missing"
        h = u.get("password_hash", "")
        assert h.startswith("$2b$"), f"hash prefix not $2b$: {h[:7]}"
        assert len(h) == 60, f"unexpected hash length {len(h)}"

    def test_seed_users_present(self):
        emails = _db_call(lambda db: db.crm_users.distinct("email"))
        for e in ["vineet@channelloyalty.ai", "chandra@channelloyalty.ai",
                  "abhinav@channelloyalty.ai", "shivam@channelloyalty.ai"]:
            assert e in emails, f"seed user missing: {e}"

    def test_login_sets_httponly_secure_cookies(self):
        r = requests.post(f"{BASE_URL}/api/crm-auth/login", json=SUPER_ADMIN)
        assert r.status_code == 200, r.text
        cookies = _set_cookie_headers(r)
        joined = " | ".join(cookies)
        assert "crm_access_token" in joined and "crm_refresh_token" in joined, joined[:300]
        for c in cookies:
            assert "HttpOnly" in c, f"cookie missing HttpOnly: {c[:120]}"
            assert "Secure" in c, f"cookie missing Secure: {c[:120]}"
        body = r.json()
        assert body.get("token")
        assert body["email"] == SUPER_ADMIN["email"]
        assert body["role"] == "super_admin"
        assert "password_hash" not in body
        assert "_id" not in body
        assert isinstance(body["id"], str)

    def test_login_body_does_not_leak_linkedin_cookies(self):
        """li_at / jsessionid are account secrets and must not be echoed to the client."""
        r = requests.post(f"{BASE_URL}/api/crm-auth/login", json=SUPER_ADMIN)
        assert r.status_code == 200
        body = r.json()
        leaked = [k for k in ("li_at", "jsessionid") if body.get(k)]
        assert not leaked, f"login response leaks LinkedIn session cookies: {leaked}"

    def test_me_with_cookie_only(self):
        s = requests.Session()
        assert s.post(f"{BASE_URL}/api/crm-auth/login", json=SUPER_ADMIN).status_code == 200
        s.headers.pop("Authorization", None)
        r = s.get(f"{BASE_URL}/api/crm-auth/me")
        assert r.status_code == 200, r.text
        assert r.json()["email"] == SUPER_ADMIN["email"]

    def test_wrong_password_401(self):
        try:
            r = requests.post(f"{BASE_URL}/api/crm-auth/login",
                              json={"email": SUPER_ADMIN["email"], "password": "definitely-wrong"})
            assert r.status_code in (401, 429), r.text
        finally:
            _clear_attempts(SUPER_ADMIN["email"])

    def test_bruteforce_lockout_after_5_fails(self):
        email = f"TEST_QA_{uuid.uuid4().hex[:8]}@example.test"
        statuses = []
        try:
            for _ in range(6):
                r = requests.post(f"{BASE_URL}/api/crm-auth/login",
                                  json={"email": email, "password": "bad"})
                statuses.append(r.status_code)
        finally:
            _clear_attempts(email)
        assert statuses[-1] == 429, f"no lockout after 5 failures: {statuses}"

    def test_cors_credentials_not_wildcard(self):
        """With allow_credentials=True the ACAO must echo the origin, never '*'."""
        origin = BASE_URL
        r = requests.post(f"{BASE_URL}/api/crm-auth/login", json=SUPER_ADMIN,
                          headers={"Origin": origin})
        assert r.status_code == 200, r.text
        h = {k.lower(): v for k, v in r.headers.items()}
        acao = h.get("access-control-allow-origin")
        print(f"CORS headers -> ACAO={acao} ACAC={h.get('access-control-allow-credentials')}")
        assert acao != "*", "wildcard ACAO with credentialed auth cookies"
        assert h.get("access-control-allow-credentials") == "true", h
