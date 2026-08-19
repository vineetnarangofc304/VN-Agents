import os
import uuid
import logging
import base64
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/company-pages", tags=["company-pages"])

mongo_url = os.environ.get('MONGO_URL', '')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'test_database')]

EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
LINKEDIN_POSTS_URL = "https://api.linkedin.com/rest/posts"
LINKEDIN_API_VERSION = "202502"

INFOGRAPHIC_DIR = Path(__file__).parent.parent / "uploads" / "company_infographics"
try:
    INFOGRAPHIC_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

# ============== Models ==============
class CompanyPageCreate(BaseModel):
    org_id: str
    name: str
    description: Optional[str] = ""
    pillars: Optional[List[str]] = []
    posts_per_day: Optional[int] = 4
    schedule_enabled: Optional[bool] = False

class ContentGenerateRequest(BaseModel):
    pillar: Optional[str] = ""
    custom_topic: Optional[str] = ""
    generate_image: Optional[bool] = True

class ManualPostRequest(BaseModel):
    content: str
    image_path: Optional[str] = None


# ============== Company Pages CRUD ==============
@router.get("")
async def list_company_pages():
    """List all configured company pages."""
    pages = []
    async for page in db.company_pages.find({}, {"_id": 0}):
        # Get post count (only published)
        post_count = await db.company_posts.count_documents({"org_id": page["org_id"], "status": "published"})
        today_count = await db.company_posts.count_documents({
            "org_id": page["org_id"],
            "status": "published",
            "posted_at": {"$gte": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()}
        })
        page["total_posts"] = post_count
        page["posts_today"] = today_count
        pages.append(page)
    return {"pages": pages}


@router.post("")
async def create_company_page(data: CompanyPageCreate):
    """Add a new company page."""
    # Sanitize org_id - strip trailing slashes and whitespace
    data.org_id = data.org_id.strip().rstrip("/")
    existing = await db.company_pages.find_one({"org_id": data.org_id})
    if existing:
        # Update instead
        await db.company_pages.update_one(
            {"org_id": data.org_id},
            {"$set": {
                "name": data.name,
                "description": data.description,
                "pillars": data.pillars,
                "posts_per_day": data.posts_per_day,
                "schedule_enabled": data.schedule_enabled,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        return {"success": True, "message": "Company page updated", "org_id": data.org_id}

    doc = {
        "org_id": data.org_id,
        "name": data.name,
        "description": data.description,
        "pillars": data.pillars or [],
        "posts_per_day": data.posts_per_day or 4,
        "schedule_enabled": data.schedule_enabled or False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_posted_at": None,
        "last_pillar_index": -1,
    }
    await db.company_pages.insert_one(doc)
    return {"success": True, "message": "Company page added", "org_id": data.org_id}


@router.put("/{org_id}")
async def update_company_page(org_id: str, data: dict):
    """Update company page settings."""
    update_fields = {}
    for field in ["name", "description", "pillars", "posts_per_day", "schedule_enabled"]:
        if field in data:
            update_fields[field] = data[field]
    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = await db.company_pages.update_one({"org_id": org_id}, {"$set": update_fields})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Company page not found")
    return {"success": True}


@router.delete("/{org_id}")
async def delete_company_page(org_id: str):
    """Remove a company page."""
    result = await db.company_pages.delete_one({"org_id": org_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Company page not found")
    return {"success": True}


# ============== Content Generation ==============
@router.post("/{org_id}/generate")
async def generate_content(org_id: str, req: ContentGenerateRequest):
    """AI-generate a post for a company page."""
    page = await db.company_pages.find_one({"org_id": org_id})
    if not page:
        raise HTTPException(status_code=404, detail="Company page not found")

    if not EMERGENT_KEY:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    pillars = page.get("pillars") or []
    pillar = req.pillar or (pillars[0] if pillars else "general industry insights")
    company_name = page.get("name", "Our Company")
    company_desc = page.get("description", "")

    # Generate post content
    try:
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"company-post-{org_id}-{uuid.uuid4()}",
            system_message=f"""You are a senior LinkedIn content strategist writing posts for {company_name}'s official company page.

Company: {company_name}
About: {company_desc}

WRITING STYLE:
- Professional, authoritative company voice — NOT personal/founder voice
- Open with a bold insight, stat, or provocative question
- Short paragraphs (1-3 lines) for mobile readability
- Include real data points and industry benchmarks where possible
- End with a CTA or thought-provoking question
- 2-3 relevant emojis max (subtle, not decorative)
- 4-6 SEO-friendly hashtags at the end
- 150-300 words — punchy, not verbose
- NEVER sound like AI. Sound like a real company sharing expertise.
- NEVER use "In today's rapidly evolving" or similar AI cliches."""
        ).with_model("openai", "gpt-4o")

        topic = req.custom_topic or pillar
        msg = UserMessage(text=f"""Write a LinkedIn post for {company_name}'s company page.

Content Pillar/Topic: {topic}

Make it keyword-rich and SEO-friendly. Include specific numbers/data where possible.
Write ONLY the post content. No meta commentary.""")

        content = await chat.send_message(msg)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Content generation error for {org_id}: {error_msg[:300]}")
        if "budget" in error_msg.lower() or "exceeded" in error_msg.lower():
            raise HTTPException(status_code=503, detail="AI budget exceeded. Go to Profile > Manage Plan > Universal Key > Add Balance to top up.")
        raise HTTPException(status_code=502, detail=f"AI generation failed: {error_msg[:200]}")

    # Generate infographic if requested
    image_path = None
    if req.generate_image:
        try:
            img_chat = LlmChat(
                api_key=EMERGENT_KEY,
                session_id=f"company-infographic-{org_id}-{uuid.uuid4()}",
                system_message=f"""You are a world-class brand designer creating vertical infographics for {company_name}'s LinkedIn.

DESIGN RULES:
1. {company_name} branding prominently at the TOP
2. Vertical format: 768x1376 pixels (LinkedIn-optimized)
3. Professional, data-driven, modern design
4. Include real data points, percentages, stats
5. Clean typography hierarchy
6. Bottom footer: company name"""
            )
            img_chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])

            img_msg = UserMessage(text=f"""Create a striking vertical infographic (768x1376) for {company_name}.

Topic based on this post:
{content[:500]}

DESIGN:
- Bold professional look
- 3-5 key statistics or data points with large bold numbers
- Clean section layout
- Footer: {company_name}""")

            text_resp, images = await img_chat.send_message_multimodal_response(img_msg)

            if images and len(images) > 0:
                image_data = base64.b64decode(images[0]['data'])
                filename = f"{org_id}_{uuid.uuid4().hex[:8]}.png"
                filepath = INFOGRAPHIC_DIR / filename
                with open(filepath, "wb") as f:
                    f.write(image_data)
                image_path = str(filepath)
                logger.info(f"Company infographic generated: {filename}")
        except Exception as e:
            logger.error(f"Infographic generation error: {e}")

    return {
        "content": content,
        "image_path": image_path,
        "pillar": pillar,
        "company": company_name,
    }


# ============== Posting ==============
@router.post("/{org_id}/post")
async def post_to_company_page(org_id: str, req: ManualPostRequest):
    """Post content to a LinkedIn company page."""
    import httpx

    page = await db.company_pages.find_one({"org_id": org_id})
    if not page:
        raise HTTPException(status_code=404, detail="Company page not found")

    # Get a valid token — use the first linkedin_account that has org posting permission
    try:
        token_doc = await db.linkedin_accounts.find_one({"schedule_enabled": True})
        if not token_doc:
            token_doc = await db.linkedin_accounts.find_one({})
    except Exception as e:
        logger.error(f"DB error fetching LinkedIn account: {e}")
        raise HTTPException(status_code=500, detail="Database error fetching LinkedIn account.")

    if not token_doc:
        raise HTTPException(status_code=400, detail="No LinkedIn account connected. Go to the LinkedIn Agent (/linkedin) and connect your account via OAuth first.")

    access_token = token_doc.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="LinkedIn token expired. Go to the LinkedIn Agent (/linkedin) and reconnect your account.")

    org_urn = f"urn:li:organization:{org_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": LINKEDIN_API_VERSION,
    }

    # Upload image if provided
    image_urn = None
    if req.image_path:
        image_file = Path(req.image_path)
        if image_file.exists():
            try:
                init_payload = {"initializeUploadRequest": {"owner": org_urn}}
                async with httpx.AsyncClient(timeout=60.0) as http_client:
                    init_resp = await http_client.post(
                        "https://api.linkedin.com/rest/images?action=initializeUpload",
                        json=init_payload, headers=headers
                    )
                if init_resp.status_code in [200, 201]:
                    init_data = init_resp.json()
                    upload_url = init_data["value"]["uploadUrl"]
                    image_urn = init_data["value"]["image"]
                    with open(image_file, "rb") as f:
                        image_bytes = f.read()
                    async with httpx.AsyncClient(timeout=60.0) as http_client:
                        await http_client.put(upload_url, content=image_bytes, headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/octet-stream",
                            "LinkedIn-Version": LINKEDIN_API_VERSION,
                        })
                else:
                    logger.error(f"Image upload init failed: {init_resp.text}")
            except Exception as e:
                logger.error(f"Image upload error: {e}")

    # Build post payload
    payload = {
        "author": org_urn,
        "commentary": req.content,
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if image_urn:
        payload["content"] = {"media": {"id": image_urn}}

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(LINKEDIN_POSTS_URL, json=payload, headers=headers)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"LinkedIn API request error ({org_id}): {error_msg}")
        # Save failed attempt
        await db.company_posts.insert_one({
            "org_id": org_id, "content": req.content, "image_path": req.image_path,
            "posted_at": datetime.now(timezone.utc).isoformat(), "status": "failed", "error": error_msg[:500],
        })
        raise HTTPException(status_code=502, detail=f"LinkedIn API connection error: {error_msg[:200]}")

    if response.status_code in [200, 201]:
        post_id = response.headers.get("x-restli-id", "")
        await db.company_posts.insert_one({
            "post_id": post_id, "org_id": org_id, "content": req.content,
            "image_path": req.image_path, "has_image": image_urn is not None,
            "posted_at": datetime.now(timezone.utc).isoformat(), "status": "published",
        })
        await db.company_pages.update_one(
            {"org_id": org_id},
            {"$set": {"last_posted_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"success": True, "post_id": post_id}
    else:
        error_text = response.text[:500]
        logger.error(f"Company post failed ({org_id}): {response.status_code} {error_text}")
        await db.company_posts.insert_one({
            "org_id": org_id, "content": req.content, "image_path": req.image_path,
            "posted_at": datetime.now(timezone.utc).isoformat(), "status": "failed", "error": error_text,
        })

        # Provide specific error messages for common issues
        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="LinkedIn token expired or missing w_organization_social permission. Go to LinkedIn Agent (/linkedin) and reconnect.")
        elif response.status_code == 403:
            raise HTTPException(status_code=403, detail="No permission to post to this company page. Ensure you are an admin and your OAuth has w_organization_social scope.")
        else:
            raise HTTPException(status_code=400, detail=f"LinkedIn API error ({response.status_code}): {error_text[:300]}")


# ============== Post History ==============
@router.get("/{org_id}/posts")
async def get_company_posts(org_id: str, limit: int = 20):
    """Get posting history for a company page."""
    posts = []
    cursor = db.company_posts.find({"org_id": org_id}, {"_id": 0}).sort("posted_at", -1).limit(limit)
    async for post in cursor:
        posts.append(post)
    return {"posts": posts}


# ============== Auto-Poster Scheduler ==============
async def run_company_auto_poster():
    """Background task: auto-post to company pages on schedule."""
    import asyncio
    await asyncio.sleep(60)  # Wait for startup

    while True:
        try:
            pages = await db.company_pages.find({"schedule_enabled": True}).to_list(50)
            now = datetime.now(timezone.utc)

            for page in pages:
                org_id = page["org_id"]
                posts_per_day = page.get("posts_per_day", 4)
                if posts_per_day <= 0:
                    continue

                # Check how many posts today
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                today_count = await db.company_posts.count_documents({
                    "org_id": org_id,
                    "status": "published",
                    "posted_at": {"$gte": today_start}
                })

                if today_count >= posts_per_day:
                    continue

                # Check time gap (spread posts evenly)
                hours_between = 24 / posts_per_day
                last_posted = page.get("last_posted_at")
                if last_posted:
                    try:
                        last_dt = datetime.fromisoformat(last_posted.replace("Z", "+00:00")) if isinstance(last_posted, str) else last_posted
                        hours_since = (now - last_dt).total_seconds() / 3600
                        if hours_since < hours_between:
                            continue
                    except Exception:
                        pass

                # Pick pillar from rotation
                pillars = page.get("pillars", [])
                if not pillars:
                    continue

                last_idx = page.get("last_pillar_index", -1)
                next_idx = (last_idx + 1) % len(pillars)
                pillar = pillars[next_idx]

                logger.info(f"Auto-posting for {page['name']} (org:{org_id}), pillar: {pillar}")

                try:
                    # Pre-check LinkedIn token BEFORE burning LLM credits
                    token_doc = await db.linkedin_accounts.find_one({"schedule_enabled": True})
                    if not token_doc:
                        token_doc = await db.linkedin_accounts.find_one({})
                    if not token_doc or not token_doc.get("access_token"):
                        logger.warning(f"Company auto-poster skipped: no LinkedIn token available")
                        break  # No point checking other pages

                    # Generate content
                    gen_req = ContentGenerateRequest(pillar=pillar, generate_image=True)
                    result = await generate_content(org_id, gen_req)

                    # Post it
                    post_req = ManualPostRequest(content=result["content"], image_path=result.get("image_path"))
                    post_result = await post_to_company_page(org_id, post_req)

                    # Update rotation index
                    await db.company_pages.update_one(
                        {"org_id": org_id},
                        {"$set": {"last_pillar_index": next_idx}}
                    )
                    logger.info(f"Auto-post published for {page['name']}: {post_result.get('post_id')}")

                except Exception as e:
                    logger.error(f"Auto-post error for {page['name']}: {e}")

        except Exception as e:
            logger.error(f"Company auto-poster error: {e}")

        import asyncio
        await asyncio.sleep(300)  # Check every 5 minutes
