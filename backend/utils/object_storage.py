"""
Emergent Object Storage utility.
Uploads and retrieves files from persistent cloud storage.
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "vnagents-crm"

_storage_key = None


def init_storage(force: bool = False):
    """Initialize storage session. Call once at startup."""
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(
        f"{STORAGE_URL}/init",
        json={"emergent_key": EMERGENT_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    logger.info("Object Storage initialized")
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Upload bytes to storage. Returns {"path": ..., "size": ..., "etag": ...}"""
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str) -> tuple:
    """Download file from storage. Returns (bytes, content_type)."""
    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60,
    )
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.get(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def upload_local_file(local_path: str, storage_path: str, content_type: str) -> dict:
    """Upload a local file to object storage."""
    with open(local_path, "rb") as f:
        data = f.read()
    return put_object(storage_path, data, content_type)


def download_to_local(storage_path: str, local_path: str) -> str:
    """Download a file from storage to a local path. Returns local_path."""
    data, _ = get_object(storage_path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(data)
    return local_path
