"""Backend tests for LinkedIn Multi-User CRM (Accounts + Data isolation)."""
import os
import pytest
import requests
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://qikberry-whatsapp.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api/li-search"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module")
def test_account(s):
    """Create a throw-away test account and clean up after tests."""
    name = f"TEST_Acct_{uuid.uuid4().hex[:6]}"
    r = s.post(f"{API}/accounts", json={"name": name})
    assert r.status_code == 200, r.text
    data = r.json()
    aid = data["account_id"]
    yield {"account_id": aid, "name": name}
    # cleanup
    s.delete(f"{API}/accounts/{aid}")


# ---------------- ACCOUNTS CRUD ----------------

class TestAccountsCRUD:
    def test_list_accounts_contains_default(self, s):
        r = s.get(f"{API}/accounts")
        assert r.status_code == 200
        accounts = r.json()["accounts"]
        assert any(a.get("account_id") == "default" for a in accounts)
        # connection_count present on all
        for a in accounts:
            assert "connection_count" in a
            assert isinstance(a["connection_count"], int)

    def test_create_account_missing_name(self, s):
        r = s.post(f"{API}/accounts", json={})
        assert r.status_code == 400

    def test_create_account_success(self, s):
        name = f"TEST_Create_{uuid.uuid4().hex[:6]}"
        r = s.post(f"{API}/accounts", json={"name": name})
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True
        assert data.get("account_id")
        assert data.get("name") == name
        # verify listed
        list_r = s.get(f"{API}/accounts")
        aids = [a["account_id"] for a in list_r.json()["accounts"]]
        assert data["account_id"] in aids
        # cleanup
        s.delete(f"{API}/accounts/{data['account_id']}")

    def test_update_account_name(self, s, test_account):
        aid = test_account["account_id"]
        new_name = test_account["name"] + "_upd"
        r = s.put(f"{API}/accounts/{aid}", json={"name": new_name})
        assert r.status_code == 200
        # verify
        list_r = s.get(f"{API}/accounts")
        acct = next((a for a in list_r.json()["accounts"] if a["account_id"] == aid), None)
        assert acct is not None
        assert acct["name"] == new_name

    def test_cannot_delete_default(self, s):
        r = s.delete(f"{API}/accounts/default")
        assert r.status_code == 400

    def test_delete_nonexistent(self, s):
        r = s.delete(f"{API}/accounts/nonexistent_xxxxx")
        assert r.status_code == 404

    def test_delete_account_removes_data(self, s):
        # create account
        name = f"TEST_Del_{uuid.uuid4().hex[:6]}"
        r = s.post(f"{API}/accounts", json={"name": name})
        aid = r.json()["account_id"]
        # push a connection
        s.post(f"{API}/connections/push", json={
            "account_id": aid,
            "connections": [{"public_id": f"delme_{uuid.uuid4().hex[:6]}", "full_name": "Del Me", "first_name": "Del", "last_name": "Me", "occupation": "Test at TestCo"}]
        })
        # delete account
        r = s.delete(f"{API}/accounts/{aid}")
        assert r.status_code == 200
        # verify not in list
        list_r = s.get(f"{API}/accounts")
        aids = [a["account_id"] for a in list_r.json()["accounts"]]
        assert aid not in aids
        # verify connections gone
        conn_r = s.get(f"{API}/connections", params={"account_id": aid})
        assert conn_r.json()["total"] == 0


# ---------------- DATA ISOLATION ----------------

class TestDataIsolation:
    def test_connections_isolated_between_accounts(self, s, test_account):
        aid = test_account["account_id"]
        pid = f"iso_{uuid.uuid4().hex[:8]}"
        # push to test account
        r = s.post(f"{API}/connections/push", json={
            "account_id": aid,
            "connections": [{
                "public_id": pid, "first_name": "Iso", "last_name": "Test",
                "full_name": "Iso Test", "occupation": "CEO at IsoCorp"
            }]
        })
        assert r.status_code == 200
        assert r.json()["new"] >= 1

        # GET on test account should return this connection
        r = s.get(f"{API}/connections", params={"account_id": aid, "keyword": pid})
        found = [c for c in r.json()["connections"] if c["public_id"] == pid]
        assert len(found) == 1
        assert found[0]["account_id"] == aid

        # GET on default should NOT return this connection
        r = s.get(f"{API}/connections", params={"account_id": "default", "keyword": pid})
        assert all(c["public_id"] != pid for c in r.json()["connections"])

    def test_stats_overview_isolated(self, s, test_account):
        aid = test_account["account_id"]
        # stats for new account should reflect only its connections
        r = s.get(f"{API}/connections/stats/overview", params={"account_id": aid})
        assert r.status_code == 200
        data = r.json()
        assert "total_connections" in data
        assert "contacted" in data
        assert "total_messages" in data
        assert "top_companies" in data
        # test account has small count; default has thousands. Compare.
        default_r = s.get(f"{API}/connections/stats/overview", params={"account_id": "default"})
        assert default_r.status_code == 200
        assert default_r.json()["total_connections"] != data["total_connections"] or data["total_connections"] == 0

    def test_enrich_scoped_to_account(self, s, test_account):
        aid = test_account["account_id"]
        pid = f"enrich_{uuid.uuid4().hex[:8]}"
        # seed a connection
        s.post(f"{API}/connections/push", json={
            "account_id": aid,
            "connections": [{"public_id": pid, "full_name": "Enrich Me", "first_name": "En", "last_name": "Me", "occupation": "X"}]
        })
        # enrich
        r = s.post(f"{API}/connections/enrich", json={
            "account_id": aid,
            "contacts": [{"public_id": pid, "email": "enrich@test.com", "phone": "1234567890"}]
        })
        assert r.status_code == 200
        assert r.json()["updated"] >= 1
        # verify
        r = s.get(f"{API}/connections", params={"account_id": aid, "keyword": pid})
        found = [c for c in r.json()["connections"] if c["public_id"] == pid]
        assert found and found[0].get("email") == "enrich@test.com"

    def test_message_queue_isolated(self, s, test_account):
        aid = test_account["account_id"]
        # queue for test account
        r = s.post(f"{API}/message/queue", json={
            "account_id": aid,
            "recipients": [{"public_id": "abc", "name": "Abc"}],
            "message": "hello TEST"
        })
        assert r.status_code == 200
        # GET queue with account_id -> should return it
        r = s.get(f"{API}/message/queue", params={"account_id": aid})
        assert r.status_code == 200
        data = r.json()
        assert data.get("message") == "hello TEST"
        # GET queue for default -> should NOT return this
        r_def = s.get(f"{API}/message/queue", params={"account_id": "default"})
        assert r_def.json().get("message") != "hello TEST"

    def test_messages_log_accepts_account_id(self, s, test_account):
        """NOTE: There is a duplicate GET /messages/log endpoint. Test which is active."""
        aid = test_account["account_id"]
        r = s.get(f"{API}/messages/log", params={"account_id": aid})
        assert r.status_code == 200
        data = r.json()
        # Newer endpoint returns {messages, total}. Older returns same shape.
        assert "messages" in data
        assert "total" in data
        # Determine which endpoint is active by checking count vs default
        # If the newer (account_id-aware) is active, our new account should have 0 msgs
        # (unless log_message was called). We haven't called log_message, so:
        r_def = s.get(f"{API}/messages/log", params={"account_id": "default"})
        # Print for diagnostic
        print(f"[diagnostic] test acct log total={data['total']}, default acct log total={r_def.json()['total']}")
        # If both return the same number regardless of account_id, then older endpoint is winning
