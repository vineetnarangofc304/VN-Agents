"""Backend tests for LinkedIn browser-script connection sync (iteration 8)."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api/li-search"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# ---- browser-script endpoint ----
def test_browser_script_returns_script_and_instructions(s):
    r = s.get(f"{API}/browser-script")
    assert r.status_code == 200
    data = r.json()
    assert "script" in data and isinstance(data["script"], str) and len(data["script"]) > 100
    assert "instructions" in data and isinstance(data["instructions"], list)
    assert len(data["instructions"]) == 7
    # script references push endpoint
    s = data["script"]
    assert "/api/li-search/connections/push" in s
    # v2 selectors
    assert 'a[href*="/in/"]' in s
    assert "closest" in s
    assert "aria-hidden" in s
    # batch sending logic (batches of 100)
    assert "slice(i, i + 100)" in s or "batch" in s.lower()
    # instructions mention scrolling/re-run
    joined = " ".join(data["instructions"]).lower()
    assert "scroll" in joined


# ---- connections/push endpoint ----
def test_push_empty_returns_400(s):
    r = s.post(f"{API}/connections/push", json={"connections": []})
    assert r.status_code == 400


def test_push_missing_field_returns_400(s):
    r = s.post(f"{API}/connections/push", json={})
    assert r.status_code == 400


def test_push_and_retrieve_connections(s):
    payload = {"connections": [
        {"full_name": "TEST Alice Aardvark", "first_name": "TEST_Alice",
         "last_name": "Aardvark", "occupation": "Test QA Engineer",
         "public_id": "test-alice-aardvark-zz1", "profile_url": "https://www.linkedin.com/in/test-alice-aardvark-zz1",
         "avatar_url": "", "urn": "urn:li:fsd_profile:test-alice-aardvark-zz1"},
        {"full_name": "TEST Bob Beetle", "first_name": "TEST_Bob",
         "last_name": "Beetle", "occupation": "Test Marketing Lead",
         "public_id": "test-bob-beetle-zz2", "profile_url": "https://www.linkedin.com/in/test-bob-beetle-zz2",
         "avatar_url": "", "urn": "urn:li:fsd_profile:test-bob-beetle-zz2"},
    ]}
    r = s.post(f"{API}/connections/push", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["success"] is True
    assert d["stored"] == 2

    # GET should list them
    r2 = s.get(f"{API}/connections", params={"count": 100})
    assert r2.status_code == 200
    data = r2.json()
    assert data["total"] >= 2
    ids = [c.get("public_id") for c in data["connections"]]
    assert "test-alice-aardvark-zz1" in ids
    assert "test-bob-beetle-zz2" in ids

    # Search by keyword
    r3 = s.get(f"{API}/connections", params={"keyword": "Aardvark"})
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["total"] >= 1
    assert any("Aardvark" in (c.get("last_name") or "") for c in d3["connections"])

    # Idempotent upsert - push again, no duplicates
    r4 = s.post(f"{API}/connections/push", json=payload)
    assert r4.status_code == 200
    r5 = s.get(f"{API}/connections", params={"keyword": "TEST_Alice"})
    assert r5.json()["total"] == 1

    # No _id leaks as ObjectId type
    for c in data["connections"]:
        assert isinstance(c.get("_id", ""), str)


# ---- regression checks ----
def test_health(s):
    r = s.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200


def test_posts_still_returns_20(s):
    r = s.get(f"{BASE_URL}/api/li-search/posts")
    assert r.status_code == 200
    d = r.json()
    assert d["stats"]["total_posts"] >= 20


# ---- cleanup ----
def test_cleanup_test_connections(s):
    """Remove test data via direct mongo since no DELETE endpoint exists."""
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME', 'agent_hub')

    async def _clean():
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        res = await db.li_connections.delete_many({"public_id": {"$regex": "^test-"}})
        client.close()
        return res.deleted_count

    n = asyncio.get_event_loop().run_until_complete(_clean())
    assert n >= 0
