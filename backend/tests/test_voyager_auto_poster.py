"""Iteration 26: Voyager auto-poster module structure + WhatsApp CTA in generated content.

Covers:
- health check
- GET /api/li-search/cookie -> Abhinav Khanna, has_cookie true
- POST /api/li-search/voyager-post empty content -> 400
- POST /api/company-pages/69021406/generate -> content contains +91-9910530372 CTA
- GET /api/company-pages -> 5 pages
- module: routes/voyager_auto_poster.py (TOPIC_PILLARS=10, FUNDLE_CONTEXT, run_voyager_auto_poster)
- asset: uploads/fundle_logo.png
"""
import os
import sys
import inspect
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
BACKEND_DIR = Path("/app/backend")
WHATSAPP_NUMBER = "9910530372"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- health ----------
def test_health(client):
    r = client.get(f"{BASE_URL}/api/health", timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("status") in ("healthy", "ok")


# ---------- li-search cookie ----------
def test_cookie_abhinav_has_cookie(client):
    r = client.get(f"{BASE_URL}/api/li-search/cookie", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "_id" not in str(data), f"Mongo _id leaked: {data}"
    assert data.get("has_cookie") is True, data
    assert data.get("profile_name") == "Abhinav Khanna", data


# ---------- voyager-post validation ----------
def test_voyager_post_empty_content_400(client):
    r = client.post(f"{BASE_URL}/api/li-search/voyager-post", json={"content": ""}, timeout=60)
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:300]}"
    assert "content" in r.json().get("detail", "").lower()


# ---------- company pages ----------
def test_company_pages_list_has_5(client):
    r = client.get(f"{BASE_URL}/api/company-pages", timeout=30)
    assert r.status_code == 200, r.text
    pages = r.json()
    if isinstance(pages, dict):
        pages = pages.get("pages", pages.get("items", []))
    assert len(pages) == 5, f"expected 5 pages got {len(pages)}"
    assert any(p.get("org_id") == "69021406" for p in pages)


def test_generate_includes_whatsapp_cta(client):
    r = client.post(
        f"{BASE_URL}/api/company-pages/69021406/generate",
        json={"generate_image": False},
        timeout=240,
    )
    assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
    data = r.json()
    content = data.get("content") or ""
    assert len(content) > 100, data
    print("GENERATED CONTENT:\n", content)
    assert WHATSAPP_NUMBER in content, f"WhatsApp CTA missing from generated content:\n{content}"
    assert "#" in content, "no hashtags in generated content"


# ---------- auto-poster module structure ----------
def test_auto_poster_module_structure():
    path = BACKEND_DIR / "routes" / "voyager_auto_poster.py"
    assert path.exists(), "voyager_auto_poster.py missing"
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    # module reads MONGO_URL/DB_NAME at import time; backend loads them via dotenv
    for k, v in dotenv_values(str(BACKEND_DIR / ".env")).items():
        if v is not None:
            os.environ.setdefault(k, v)
    from routes import voyager_auto_poster as vap

    assert isinstance(vap.TOPIC_PILLARS, list)
    assert len(vap.TOPIC_PILLARS) == 10, f"expected 10 pillars got {len(vap.TOPIC_PILLARS)}"
    assert all(isinstance(p, str) and len(p) > 40 for p in vap.TOPIC_PILLARS)
    assert len(set(vap.TOPIC_PILLARS)) == 10, "duplicate pillars"

    ctx = vap.FUNDLE_CONTEXT
    for token in ["Fundle Brain", "Fundle Retail AI", "Fundle Mall AI", "Loyalty Agent",
                  "Lead Agent", "KAZO", "ADSR", "Abhinav Khanna"]:
        assert token in ctx, f"FUNDLE_CONTEXT missing '{token}'"

    assert WHATSAPP_NUMBER in vap.WHATSAPP_CTA
    assert inspect.iscoroutinefunction(vap.run_voyager_auto_poster)
    for fn in ("_get_voyager_session", "_generate_post_content", "_generate_infographic",
               "_upload_and_post_voyager"):
        assert inspect.iscoroutinefunction(getattr(vap, fn)), fn


def test_auto_poster_wired_into_startup():
    src = (BACKEND_DIR / "server.py").read_text()
    assert "from routes.voyager_auto_poster import run_voyager_auto_poster" in src
    assert "create_task(run_voyager_auto_poster())" in src


def test_fundle_logo_asset_exists():
    logo = BACKEND_DIR / "uploads" / "fundle_logo.png"
    assert logo.exists(), "fundle_logo.png missing"
    size = logo.stat().st_size
    assert size > 5000, f"logo suspiciously small: {size} bytes"
    with open(logo, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n", "not a valid PNG"
