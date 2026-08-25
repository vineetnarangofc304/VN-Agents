"""
LinkedIn CRM — Multi-User Auth System
JWT + bcrypt, cookie-based sessions, role-based access (super_admin / user)
"""
import os
import secrets
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crm-auth", tags=["crm-auth"])

mongo_url = os.environ.get("MONGO_URL", "")
_client = AsyncIOMotorClient(mongo_url)
_db = _client[os.environ.get("DB_NAME", "test_database")]

JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = 60  # minutes
REFRESH_TOKEN_EXPIRE = 7  # days
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

DEFAULT_PASSWORD = "CRM@2026!"

SEED_USERS = [
    {"name": "Vineet Narang", "email": "vineet@channelloyalty.ai", "role": "super_admin"},
    {"name": "Chandra", "email": "chandra@channelloyalty.ai", "role": "user"},
    {"name": "Abhinav", "email": "abhinav@channelloyalty.ai", "role": "user"},
    {"name": "Shivam", "email": "shivam@channelloyalty.ai", "role": "user"},
]


# ============ Helpers ============
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id, "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE),
        "type": "refresh",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("crm_access_token", access, httponly=True, secure=True, samesite="none", max_age=ACCESS_TOKEN_EXPIRE * 60, path="/")
    response.set_cookie("crm_refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=REFRESH_TOKEN_EXPIRE * 86400, path="/")


def _user_to_dict(user: dict) -> dict:
    u = {**user}
    u["id"] = str(u.pop("_id"))
    u.pop("password_hash", None)
    return u


# ============ Auth Dependency ============
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("crm_access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await _db.crm_users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return _user_to_dict(user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_super_admin(request: Request) -> dict:
    user = await get_current_user(request)
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    return user


# ============ Brute Force ============
async def _check_lockout(ip: str, email: str):
    key = f"{email}"  # Use email only (IP varies behind k8s ingress)
    doc = await _db.crm_login_attempts.find_one({"identifier": key})
    if doc and doc.get("count", 0) >= MAX_LOGIN_ATTEMPTS:
        locked_until = doc.get("locked_until")
        if locked_until:
            # Normalize tz-naive datetime from MongoDB
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < locked_until:
                remaining = int((locked_until - datetime.now(timezone.utc)).total_seconds() / 60)
                raise HTTPException(status_code=429, detail=f"Too many attempts. Try again in {remaining + 1} minutes.")
        await _db.crm_login_attempts.delete_one({"identifier": key})


async def _record_failed(ip: str, email: str):
    key = f"{email}"
    await _db.crm_login_attempts.update_one(
        {"identifier": key},
        {"$inc": {"count": 1}, "$set": {"locked_until": datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)}},
        upsert=True,
    )


async def _clear_attempts(ip: str, email: str):
    await _db.crm_login_attempts.delete_one({"identifier": f"{email}"})


# ============ Endpoints ============
@router.post("/login")
async def login(data: dict, request: Request, response: Response):
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    ip = request.client.host if request.client else "unknown"
    await _check_lockout(ip, email)

    user = await _db.crm_users.find_one({"email": email})
    if not user or not verify_password(password, user["password_hash"]):
        await _record_failed(ip, email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await _clear_attempts(ip, email)

    uid = str(user["_id"])
    access = create_access_token(uid, email)
    refresh = create_refresh_token(uid)
    _set_auth_cookies(response, access, refresh)

    return _user_to_dict(user)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("crm_access_token", path="/")
    response.delete_cookie("crm_refresh_token", path="/")
    return {"success": True}


@router.get("/me")
async def me(request: Request):
    user = await get_current_user(request)
    return user


@router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("crm_refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await _db.crm_users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        access = create_access_token(str(user["_id"]), user["email"])
        response.set_cookie("crm_access_token", access, httponly=True, secure=True, samesite="none", max_age=ACCESS_TOKEN_EXPIRE * 60, path="/")
        return _user_to_dict(user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.post("/change-password")
async def change_password(data: dict, request: Request):
    user = await get_current_user(request)
    current = data.get("current_password", "")
    new_pw = data.get("new_password", "")
    if not current or not new_pw:
        raise HTTPException(status_code=400, detail="Current and new password required")
    if len(new_pw) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    full_user = await _db.crm_users.find_one({"_id": ObjectId(user["id"])})
    if not verify_password(current, full_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    await _db.crm_users.update_one(
        {"_id": ObjectId(user["id"])},
        {"$set": {"password_hash": hash_password(new_pw)}}
    )
    return {"success": True, "detail": "Password changed"}


# ============ Super Admin: User Management ============
@router.get("/users")
async def list_users(request: Request):
    await require_super_admin(request)
    users = []
    async for u in _db.crm_users.find({}, {"password_hash": 0}):
        u["id"] = str(u.pop("_id"))
        users.append(u)
    return {"users": users}


@router.post("/users")
async def create_user(data: dict, request: Request):
    await require_super_admin(request)
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    password = data.get("password", DEFAULT_PASSWORD)
    role = data.get("role", "user")
    li_at = data.get("li_at", "")
    jsessionid = data.get("jsessionid", "")

    if not email or not name:
        raise HTTPException(status_code=400, detail="Name and email required")
    if await _db.crm_users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already exists")

    doc = {
        "name": name, "email": email,
        "password_hash": hash_password(password),
        "role": role,
        "li_at": li_at, "jsessionid": jsessionid,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await _db.crm_users.insert_one(doc)
    return {"success": True, "user_id": str(result.inserted_id)}


@router.put("/users/{user_id}")
async def update_user(user_id: str, data: dict, request: Request):
    await require_super_admin(request)
    fields = {}
    for k in ["name", "email", "role", "li_at", "jsessionid"]:
        if k in data:
            fields[k] = data[k]
    if "password" in data and data["password"]:
        fields["password_hash"] = hash_password(data["password"])
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await _db.crm_users.update_one({"_id": ObjectId(user_id)}, {"$set": fields})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, request: Request):
    admin = await require_super_admin(request)
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    await _db.crm_users.delete_one({"_id": ObjectId(user_id)})
    return {"success": True}


# ============ Seed ============
async def seed_crm_users():
    """Seed initial CRM users if they don't exist."""
    try:
        await _db.crm_users.create_index("email", unique=True)
        await _db.crm_login_attempts.create_index("identifier")

        for seed in SEED_USERS:
            existing = await _db.crm_users.find_one({"email": seed["email"]})
            if not existing:
                await _db.crm_users.insert_one({
                    "name": seed["name"],
                    "email": seed["email"],
                    "password_hash": hash_password(DEFAULT_PASSWORD),
                    "role": seed["role"],
                    "li_at": "",
                    "jsessionid": "",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.info(f"CRM user seeded: {seed['name']} ({seed['email']})")
    except Exception as e:
        logger.error(f"CRM user seed error: {e}")
