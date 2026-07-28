"""Iteration 10 - test 3 connections with unique public_id but empty urn (messaging select-all fix)."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api/li-search"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


def test_push_3_connections_empty_urn(s):
    payload = {"connections": [
        {"full_name": "TEST Selectall One", "first_name": "TEST_Sel1", "last_name": "One",
         "occupation": "QA1", "public_id": "test-selall-one-01",
         "profile_url": "https://www.linkedin.com/in/test-selall-one-01",
         "avatar_url": "", "urn": ""},
        {"full_name": "TEST Selectall Two", "first_name": "TEST_Sel2", "last_name": "Two",
         "occupation": "QA2", "public_id": "test-selall-two-02",
         "profile_url": "https://www.linkedin.com/in/test-selall-two-02",
         "avatar_url": "", "urn": ""},
        {"full_name": "TEST Selectall Three", "first_name": "TEST_Sel3", "last_name": "Three",
         "occupation": "QA3", "public_id": "test-selall-three-03",
         "profile_url": "https://www.linkedin.com/in/test-selall-three-03",
         "avatar_url": "", "urn": ""},
    ]}
    r = s.post(f"{API}/connections/push", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["success"] is True
    assert d["stored"] == 3


def test_get_returns_all_3_distinct_public_ids(s):
    r = s.get(f"{API}/connections", params={"keyword": "TEST_Sel", "count": 100})
    assert r.status_code == 200
    data = r.json()
    ids = [c.get("public_id") for c in data["connections"] if c.get("public_id", "").startswith("test-selall-")]
    assert set(ids) == {"test-selall-one-01", "test-selall-two-02", "test-selall-three-03"}
    # verify urns are empty (as pushed)
    for c in data["connections"]:
        if c.get("public_id", "").startswith("test-selall-"):
            assert c.get("urn", "") == ""
    # ensure no ObjectId leaks
    for c in data["connections"]:
        assert isinstance(c.get("_id", ""), str)


def test_health(s):
    r = s.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200
    assert r.json().get("status") == "healthy"


def test_posts_regression(s):
    r = s.get(f"{BASE_URL}/api/li-search/posts")
    assert r.status_code == 200
    d = r.json()
    assert d["stats"]["total_posts"] >= 20


def test_cleanup(s):
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import dotenv_values
    env = dotenv_values("/app/backend/.env")
    mongo_url = env.get('MONGO_URL') or os.environ.get('MONGO_URL')
    db_name = env.get('DB_NAME') or os.environ.get('DB_NAME', 'agent_hub')

    async def _clean():
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        res = await db.li_connections.delete_many({"public_id": {"$regex": "^test-"}})
        client.close()
        return res.deleted_count

    n = asyncio.get_event_loop().run_until_complete(_clean())
    assert n >= 0
    print(f"Cleaned {n} test connections")
