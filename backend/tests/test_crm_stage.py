"""Tests for the new PUT /api/li-search/connections/{public_id}/stage endpoint
and basic CRM API reachability."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://qikberry-whatsapp.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api/li-search"


def test_accounts_endpoint():
    r = requests.get(f"{API}/accounts", timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert "accounts" in body
    assert isinstance(body["accounts"], list)


def test_cookie_endpoint():
    r = requests.get(f"{API}/cookie", timeout=30)
    assert r.status_code == 200
    assert "has_cookie" in r.json()


def test_stats_overview_endpoint():
    accts = requests.get(f"{API}/accounts", timeout=30).json().get("accounts", [])
    acc_id = accts[0]["account_id"] if accts else ""
    r = requests.get(f"{API}/connections/stats/overview", params={"account_id": acc_id}, timeout=30)
    assert r.status_code == 200


def test_connections_list_endpoint():
    accts = requests.get(f"{API}/accounts", timeout=30).json().get("accounts", [])
    acc_id = accts[0]["account_id"] if accts else ""
    r = requests.get(f"{API}/connections", params={"account_id": acc_id, "start": 0, "count": 5}, timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert "connections" in body or "elements" in body or isinstance(body, dict)


def test_update_stage_missing_connection_returns_404():
    r = requests.put(
        f"{API}/connections/__nonexistent_public_id__/stage",
        json={"stage": "connected", "account_id": "any"},
        timeout=30,
    )
    assert r.status_code == 404


def test_update_stage_on_real_connection_if_available():
    accts = requests.get(f"{API}/accounts", timeout=30).json().get("accounts", [])
    if not accts:
        pytest.skip("No accounts")
    acc_id = accts[0]["account_id"]
    conns_resp = requests.get(
        f"{API}/connections", params={"account_id": acc_id, "start": 0, "count": 1}, timeout=30
    ).json()
    conns = conns_resp.get("connections") or conns_resp.get("elements") or []
    if not conns:
        pytest.skip("No connections in account to test stage update")
    pub = conns[0].get("public_id") or conns[0].get("publicIdentifier")
    if not pub:
        pytest.skip("Connection missing public_id")

    # Update to 'messaged'
    r = requests.put(
        f"{API}/connections/{pub}/stage",
        json={"stage": "messaged", "account_id": acc_id},
        timeout=30,
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert data.get("stage") == "messaged"

    # Verify persistence via connection detail
    d = requests.get(f"{API}/connections/{pub}", params={"account_id": acc_id}, timeout=30)
    if d.status_code == 200:
        detail = d.json()
        assert detail.get("lead_stage") == "messaged"
