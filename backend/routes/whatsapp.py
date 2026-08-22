"""
Qikchat WhatsApp Integration for CRM.
Sends WhatsApp messages via the Qikchat API (api.qikchat.in).
"""
import os
import re
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

mongo_url = os.environ.get("MONGO_URL", "")
_client = AsyncIOMotorClient(mongo_url)
_db = _client[os.environ.get("DB_NAME", "test_database")]

QIKCHAT_API_URL = "https://api.qikchat.in/v1/messages"

# Phone validation: digits only after optional +, 10-15 digits
_PHONE_RE = re.compile(r"^\+?\d{10,15}$")


def _get_api_key():
    return os.environ.get("QIKCHAT_API_KEY", "")


def _get_headers():
    key = _get_api_key()
    if not key:
        raise HTTPException(status_code=400, detail="QIKCHAT_API_KEY not configured. Add it in Settings.")
    return {"QIKCHAT-API-KEY": key, "Content-Type": "application/json"}


def _normalize_phone(raw: str) -> str:
    """Normalize and validate phone number."""
    phone = raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not phone.startswith("+"):
        if phone.startswith("91") and len(phone) >= 12:
            phone = f"+{phone}"
        else:
            phone = f"+91{phone}"
    if not _PHONE_RE.match(phone):
        raise HTTPException(status_code=400, detail=f"Invalid phone number: {raw}")
    return phone


async def _send_one(phone: str, message: str, contact_name: str, headers: dict) -> dict:
    """Send a single WhatsApp message and log it. Returns result dict."""
    payload = {
        "to_contact": phone,
        "type": "text",
        "text": {"body": message[:4096]},
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(QIKCHAT_API_URL, json=payload, headers=headers)
        resp_data = resp.json()
    except httpx.TimeoutException:
        log_entry = {
            "id": str(uuid.uuid4()), "phone": phone, "contact_name": contact_name,
            "message": message, "channel": "whatsapp", "status": "failed",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        await _db.whatsapp_messages.insert_one(log_entry)
        return {"success": False, "detail": "Qikchat API timed out"}
    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")
        return {"success": False, "detail": str(e)}

    queued = resp.status_code == 200 and resp_data.get("status")
    log_entry = {
        "id": str(uuid.uuid4()),
        "phone": phone,
        "contact_name": contact_name,
        "message": message,
        "channel": "whatsapp",
        "status": "queued" if queued else "failed",
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.whatsapp_messages.insert_one(log_entry)

    if queued:
        msg_data = resp_data.get("data", [{}])[0]
        return {
            "success": True,
            "detail": "Message queued for delivery",
            "message_id": msg_data.get("id", ""),
            "credits_used": msg_data.get("credits", 0),
        }
    return {"success": False, "detail": resp_data.get("message", "Failed to send")}


# ============== Config ==============
@router.get("/config")
async def get_whatsapp_config():
    """Check if WhatsApp is configured."""
    return {"configured": bool(_get_api_key()), "api_key_set": bool(_get_api_key())}


# ============== Send Messages ==============
@router.post("/send")
async def send_whatsapp_message(data: dict):
    """Send a WhatsApp text message via Qikchat."""
    raw_phone = data.get("phone", "").strip()
    message = data.get("message", "").strip()
    contact_name = data.get("contact_name", "")

    if not raw_phone:
        raise HTTPException(status_code=400, detail="Phone number required")
    if not message:
        raise HTTPException(status_code=400, detail="Message body required")

    phone = _normalize_phone(raw_phone)
    headers = _get_headers()
    result = await _send_one(phone, message, contact_name, headers)

    if not result["success"]:
        return result
    return result


@router.post("/send-bulk")
async def send_bulk_whatsapp(data: dict):
    """Send WhatsApp messages to multiple contacts (max 50 per batch)."""
    contacts = data.get("contacts", [])
    message_template = data.get("message", "")

    if not contacts:
        raise HTTPException(status_code=400, detail="No contacts provided")
    if not message_template:
        raise HTTPException(status_code=400, detail="Message template required")
    if len(contacts) > 50:
        raise HTTPException(status_code=400, detail="Max 50 contacts per batch")

    headers = _get_headers()
    results = []

    for contact in contacts:
        raw_phone = contact.get("phone", "").strip()
        name = contact.get("name", "there")

        if not raw_phone:
            results.append({"phone": raw_phone, "name": name, "status": "skipped", "error": "No phone"})
            continue

        try:
            phone = _normalize_phone(raw_phone)
        except HTTPException:
            results.append({"phone": raw_phone, "name": name, "status": "skipped", "error": "Invalid phone"})
            continue

        msg = message_template.replace("{name}", name.split()[0] if name else "there")
        result = await _send_one(phone, msg, name, headers)
        results.append({
            "phone": phone, "name": name,
            "status": "queued" if result["success"] else "failed",
            "message_id": result.get("message_id"),
        })

    queued = sum(1 for r in results if r["status"] == "queued")
    return {"success": True, "total": len(results), "sent": queued, "failed": len(results) - queued, "results": results}


# ============== Message History ==============
@router.get("/messages")
async def get_whatsapp_messages(limit: int = 50, skip: int = 0):
    """Get WhatsApp message history."""
    messages = []
    async for m in _db.whatsapp_messages.find({}, {"_id": 0}).sort("sent_at", -1).skip(skip).limit(limit):
        messages.append(m)
    total = await _db.whatsapp_messages.count_documents({})
    return {"messages": messages, "total": total}


@router.get("/stats")
async def get_whatsapp_stats():
    """Get WhatsApp messaging stats."""
    total = await _db.whatsapp_messages.count_documents({})
    queued = await _db.whatsapp_messages.count_documents({"status": "queued"})
    failed = await _db.whatsapp_messages.count_documents({"status": "failed"})
    return {"total": total, "sent": queued, "failed": failed}
