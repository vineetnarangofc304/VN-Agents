"""Brute-force lockout + CORS credential checks for CRM auth (playbook items)."""
import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env["REACT_APP_BACKEND_URL"]).rstrip("/")
ORIGIN = BASE_URL


def test_brute_force_lockout_after_5_failures():
    email = "TEST_lockout_probe@example.com"
    codes = []
    for _ in range(7):
        r = requests.post(f"{BASE_URL}/api/crm-auth/login", json={"email": email, "password": "bad"}, timeout=30)
        codes.append(r.status_code)
    assert 429 in codes, f"No lockout (429) after 7 failed attempts. Codes: {codes}"
    # cleanup
    from pymongo import MongoClient
    env = dotenv_values("/app/backend/.env")
    c = MongoClient(os.environ.get("MONGO_URL") or env["MONGO_URL"])
    c[os.environ.get("DB_NAME") or env["DB_NAME"]].crm_login_attempts.delete_one({"identifier": email.lower()})
    c.close()


def test_cors_allows_credentials_with_explicit_origin():
    r = requests.options(
        f"{BASE_URL}/api/crm-auth/login",
        headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "content-type"},
        timeout=30,
    )
    assert r.status_code in (200, 204), r.status_code
    allow_origin = r.headers.get("access-control-allow-origin")
    assert allow_origin == ORIGIN, f"allow-origin={allow_origin} (must be explicit origin, not *)"
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_seed_does_not_reset_existing_admin_password():
    """Informational: seed_crm_users only inserts, never updates existing users."""
    import re
    src = open("/app/backend/routes/crm_auth.py").read()
    assert "update_one" in src.split("async def seed_crm_users")[1], \
        "seed_crm_users does not update existing admin password if DEFAULT_PASSWORD changes"
