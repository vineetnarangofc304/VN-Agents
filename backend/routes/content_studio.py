import os
import logging
import asyncio
import json
import uuid
import secrets
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/content-studio", tags=["content-studio"])

mongo_url = os.environ.get('MONGO_URL', '')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'agent_hub')]

EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# LinkedIn OAuth config (separate from Abhinav's)
CS_LINKEDIN_CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID")
CS_LINKEDIN_CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET")
CS_LINKEDIN_REDIRECT_URI = os.environ.get("REACT_APP_BACKEND_URL", "") + "/api/content-studio/oauth/callback" if os.environ.get("REACT_APP_BACKEND_URL") else os.environ.get("LINKEDIN_REDIRECT_URI", "").replace("/api/linkedin/callback", "/api/content-studio/oauth/callback")
LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
LINKEDIN_POSTS_URL = "https://api.linkedin.com/rest/posts"
LINKEDIN_API_VERSION = "202502"

ABOUT_ME = """Vineet Narang — Founder building multiple AI-first enterprise businesses.
Current businesses: FundleBrain, ChannelLoyalty.ai, HearClear India, FundleReach, HomeIVF, AI Recruitment Platform, Marketplace Commission Automation, Enterprise Retail OS, MBO OS, AI Finance & Reconciliation, AI SEO Platform, AI CRM, AI Analytics, AI Loyalty Platform.
Previously founded m'loyal (MobiQuest), one of India's largest loyalty platforms, later acquired by Paytm.
Positioning: AI is becoming the operating system of modern enterprises. We build Enterprise AI Systems, AI Workers, Multi-Agent Systems, Autonomous Business Processes."""

CONTENT_PILLARS = [
    {"id": "enterprise-ai", "name": "Enterprise AI", "color": "#0066FF"},
    {"id": "agentic-ai", "name": "Agentic AI", "color": "#6366F1"},
    {"id": "multi-agent", "name": "Multi-Agent Systems", "color": "#8B5CF6"},
    {"id": "retail-ai", "name": "Retail AI", "color": "#EC4899"},
    {"id": "healthcare-ai", "name": "Healthcare AI", "color": "#10B981"},
    {"id": "recruitment-ai", "name": "Recruitment AI", "color": "#F59E0B"},
    {"id": "finance-ai", "name": "Finance AI", "color": "#06B6D4"},
    {"id": "loyalty-ai", "name": "Loyalty Platforms", "color": "#EF4444"},
    {"id": "crm-automation", "name": "CRM Automation", "color": "#14B8A6"},
    {"id": "customer-analytics", "name": "Customer Analytics", "color": "#7C3AED"},
    {"id": "marketplace-auto", "name": "Marketplace Automation", "color": "#D946EF"},
    {"id": "digital-transform", "name": "Digital Transformation", "color": "#0EA5E9"},
    {"id": "ai-strategy", "name": "AI Strategy", "color": "#059669"},
    {"id": "product-thinking", "name": "Product Thinking", "color": "#DC2626"},
    {"id": "startup-lessons", "name": "Startup Lessons", "color": "#CA8A04"},
    {"id": "future-of-work", "name": "Future of Work", "color": "#2563EB"},
    {"id": "voice-ai", "name": "Voice AI & WhatsApp AI", "color": "#16A34A"},
    {"id": "ai-governance", "name": "AI Governance", "color": "#475569"},
]

CONTENT_TYPES = [
    "linkedin-post", "linkedin-article", "carousel", "infographic",
    "architecture-diagram", "case-study", "whitepaper", "framework",
    "comparison-chart", "video-script", "newsletter", "twitter-thread",
]


# ============== Models ==============
class GenerateRequest(BaseModel):
    pillar: str
    content_type: str = "linkedin-post"
    topic_hint: Optional[str] = None
    tone: str = "authoritative-yet-conversational"


class CalendarGenerateRequest(BaseModel):
    days: int = 30


class PublishRequest(BaseModel):
    post_id: str
    include_image: bool = False


# ============== AI Generation Pipeline ==============

async def _step_research(pillar: str, topic_hint: str = "") -> str:
    """Step 1: Research — gather context and angles."""
    pillar_name = next((p["name"] for p in CONTENT_PILLARS if p["id"] == pillar), pillar)
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"cs-research-{uuid.uuid4()}",
        system_message=f"""You are a senior enterprise AI researcher working for Vineet Narang.

{ABOUT_ME}

Your job: Research and identify the most compelling, original angle for a LinkedIn post about {pillar_name}.

Think about:
- What's actually happening in the industry RIGHT NOW
- What misconceptions exist that Vineet can correct
- What real patterns he's seeing from building enterprise AI systems
- What frameworks or mental models would be valuable
- What would make a CXO or enterprise leader stop scrolling

Return a JSON object:
{{"topic": "specific topic title", "angle": "the unique angle/thesis", "key_points": ["point1", "point2", "point3", "point4"], "hook_ideas": ["hook1", "hook2"], "data_points": ["stat or example 1", "stat or example 2"], "target_resonance": "who will this resonate most with and why"}}"""
    ).with_model("openai", "gpt-4o")

    prompt = f"Research a compelling topic for {pillar_name}."
    if topic_hint:
        prompt += f" Direction: {topic_hint}"
    prompt += " Find an angle that feels like it comes from someone actually building these systems, not commenting from the sidelines."

    msg = UserMessage(text=prompt)
    response = await chat.send_message(msg)
    return response


async def _step_draft(research_output: str, content_type: str, tone: str) -> str:
    """Step 2: Draft — write the full content."""
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"cs-draft-{uuid.uuid4()}",
        system_message=f"""You are Vineet Narang's personal ghostwriter. You write content that sounds exactly like a founder who builds enterprise AI systems every day.

{ABOUT_ME}

VOICE RULES:
- First person. Always "I" or "We" — never third person.
- Conversational but authoritative. Like explaining to a smart peer over coffee.
- Technical depth without jargon overload. Show you KNOW the architecture.
- Real examples from building. "When we built X for Y, we found..."
- Contrarian where appropriate. Challenge conventional wisdom.
- Frameworks and mental models. Give people tools to think, not just opinions.
- Short paragraphs. 1-3 sentences max per paragraph.
- Strong hook in first line. Pattern interrupt.
- Memorable conclusion. End with a sharp insight or provocative question.

NEVER DO:
- Generic AI hype ("AI is transforming everything!")
- Motivational fluff ("The future belongs to those who...")
- Buzzword salads
- Listicles without substance
- Empty platitudes
- Hashtag spam (max 3 relevant hashtags at end)
- Emoji overuse (0-2 max, strategically placed)

CONTENT TYPE: {content_type}
TONE: {tone}"""
    ).with_model("openai", "gpt-4o")

    msg = UserMessage(text=f"""Based on this research, write the full content:

{research_output}

Write the complete post. Make it feel like it comes from real experience building enterprise AI. Include specific technical details, architecture thinking, or business insights that only someone actually building these systems would know.""")
    response = await chat.send_message(msg)
    return response


async def _step_review(draft: str, pillar: str) -> str:
    """Step 3: Review & Polish — quality check and brand alignment."""
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"cs-review-{uuid.uuid4()}",
        system_message=f"""You are a world-class content editor and brand strategist. Your job is to review and improve content for Vineet Narang.

{ABOUT_ME}

REVIEW CRITERIA:
1. Does the hook STOP scrolling? (First 2 lines visible in feed)
2. Is there ORIGINAL thinking? (Not recycled AI commentary)
3. Are there SPECIFIC examples? (Architecture details, business outcomes)
4. Does it establish AUTHORITY? (Builder credibility, not commentator)
5. Is the conclusion MEMORABLE? (Sharp insight, not generic)
6. Is formatting SCANNABLE? (Short paragraphs, visual breaks)
7. Does it TEACH something? (Reader leaves smarter)
8. Would a CXO SHARE this? (Valuable enough to forward)

Return JSON:
{{"score": 1-10, "improved_content": "the polished version", "changes_made": ["change1", "change2"], "strengths": ["str1"], "weaknesses_fixed": ["fix1"]}}"""
    ).with_model("openai", "gpt-4o")

    msg = UserMessage(text=f"Review and polish this {pillar} content. Fix anything that feels generic, weak, or AI-generated. Make it sharper:\n\n{draft}")
    response = await chat.send_message(msg)
    return response


async def _generate_infographic_spec(post_content: str, pillar: str) -> str:
    """Generate infographic specification for Nano Banana."""
    pillar_name = next((p["name"] for p in CONTENT_PILLARS if p["id"] == pillar), pillar)
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"cs-infographic-{uuid.uuid4()}",
        system_message="""You design world-class infographic specifications. McKinsey quality. Stripe quality. Apple quality.

DESIGN RULES:
- White background (#FFFFFF)
- Primary blue (#0066FF) for highlights and accents
- Dark text (#09090B) for headings
- Muted gray (#52525B) for body text
- Clean sans-serif typography (like Inter or SF Pro)
- Minimal. No clipart. No cartoons. No stock photos.
- Enterprise icons. Simple geometric shapes.
- Architecture diagrams use clean boxes, arrows, flow lines
- Data visualizations use simple bar/line charts
- Maximum 5-6 key points visible
- Clear visual hierarchy
- Generous whitespace
- Professional. Could appear in a board presentation.

Return a detailed image generation prompt that will produce this infographic."""
    ).with_model("openai", "gpt-4o")

    msg = UserMessage(text=f"Create an infographic specification for this {pillar_name} content:\n\n{post_content[:1500]}\n\nDesign a professional, enterprise-grade infographic that visualizes the key concepts.")
    response = await chat.send_message(msg)
    return response


# ============== API Endpoints ==============

@router.get("/pillars")
async def get_pillars():
    """Get all content pillars."""
    return {"pillars": CONTENT_PILLARS}


@router.get("/stats")
async def get_stats():
    """Get content studio dashboard stats."""
    total_posts = await db.cs_posts.count_documents({})
    published = await db.cs_posts.count_documents({"status": "published"})
    drafts = await db.cs_posts.count_documents({"status": "draft"})
    scheduled = await db.cs_calendar.count_documents({"status": "scheduled"})
    this_week = await db.cs_posts.count_documents({
        "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=7)}
    })

    # Pillar distribution
    pipeline = [
        {"$group": {"_id": "$pillar", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    pillar_dist = {}
    async for doc in db.cs_posts.aggregate(pipeline):
        pillar_dist[doc["_id"]] = doc["count"]

    return {
        "total_posts": total_posts,
        "published": published,
        "drafts": drafts,
        "scheduled": scheduled,
        "this_week": this_week,
        "pillar_distribution": pillar_dist
    }


@router.post("/generate")
async def generate_content(req: GenerateRequest):
    """Multi-step AI content generation pipeline."""
    if not EMERGENT_KEY:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    post_id = str(uuid.uuid4())
    pillar_name = next((p["name"] for p in CONTENT_PILLARS if p["id"] == req.pillar), req.pillar)

    # Store initial record
    post_doc = {
        "post_id": post_id,
        "pillar": req.pillar,
        "pillar_name": pillar_name,
        "content_type": req.content_type,
        "status": "generating",
        "step": "research",
        "created_at": datetime.now(timezone.utc),
    }
    await db.cs_posts.insert_one(post_doc)

    # Run pipeline in background
    asyncio.create_task(_run_generation_pipeline(post_id, req))

    return {"post_id": post_id, "status": "generating"}


async def _run_generation_pipeline(post_id: str, req: GenerateRequest):
    """Background generation pipeline."""
    try:
        # Step 1: Research
        await db.cs_posts.update_one({"post_id": post_id}, {"$set": {"step": "research"}})
        research_raw = await _step_research(req.pillar, req.topic_hint or "")

        # Parse research JSON
        research_data = research_raw
        try:
            if "```" in research_raw:
                research_raw_clean = research_raw.split("```")[1].replace("json", "").strip()
            else:
                research_raw_clean = research_raw
            research_parsed = json.loads(research_raw_clean)
        except:
            research_parsed = {"topic": "Generated Topic", "angle": research_raw[:200]}

        await db.cs_posts.update_one({"post_id": post_id}, {"$set": {
            "step": "drafting",
            "research": research_parsed,
            "research_raw": research_data
        }})

        # Step 2: Draft
        draft = await _step_draft(research_data, req.content_type, req.tone if hasattr(req, 'tone') else "authoritative-yet-conversational")

        await db.cs_posts.update_one({"post_id": post_id}, {"$set": {
            "step": "reviewing",
            "draft": draft
        }})

        # Step 3: Review & Polish
        review_raw = await _step_review(draft, req.pillar)

        # Parse review JSON
        try:
            if "```" in review_raw:
                review_clean = review_raw.split("```")[1].replace("json", "").strip()
            else:
                review_clean = review_raw
            review_data = json.loads(review_clean)
            final_content = review_data.get("improved_content", draft)
            score = review_data.get("score", 7)
            review_notes = review_data
        except:
            final_content = draft
            score = 7
            review_notes = {"raw": review_raw}

        # Extract title from research
        title = ""
        if isinstance(research_parsed, dict):
            title = research_parsed.get("topic", "")

        await db.cs_posts.update_one({"post_id": post_id}, {"$set": {
            "status": "draft",
            "step": "complete",
            "title": title,
            "content": final_content,
            "draft": draft,
            "review": review_notes,
            "quality_score": score,
            "completed_at": datetime.now(timezone.utc)
        }})

        logger.info(f"Content generated: {post_id} — score {score}/10")

    except Exception as e:
        logger.error(f"Generation failed for {post_id}: {e}")
        await db.cs_posts.update_one({"post_id": post_id}, {"$set": {
            "status": "error",
            "step": "failed",
            "error": str(e)
        }})


@router.get("/posts/{post_id}/status")
async def get_post_status(post_id: str):
    """Get generation status for a post."""
    doc = await db.cs_posts.find_one({"post_id": post_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Post not found")
    doc["_id"] = str(doc["_id"])
    for k in ["created_at", "completed_at"]:
        if isinstance(doc.get(k), datetime):
            doc[k] = doc[k].isoformat()
    return doc


@router.get("/posts")
async def get_posts(
    status: Optional[str] = None,
    pillar: Optional[str] = None,
    content_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 20
):
    """Get all content posts."""
    query = {}
    if status and status != "all":
        query["status"] = status
    if pillar and pillar != "all":
        query["pillar"] = pillar
    if content_type and content_type != "all":
        query["content_type"] = content_type

    total = await db.cs_posts.count_documents(query)
    cursor = db.cs_posts.find(query).sort("created_at", -1).skip(skip).limit(limit)
    posts = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        for k in ["created_at", "completed_at"]:
            if isinstance(doc.get(k), datetime):
                doc[k] = doc[k].isoformat()
        posts.append(doc)

    return {"posts": posts, "total": total}


@router.put("/posts/{post_id}")
async def update_post(post_id: str, data: dict):
    """Update post content."""
    updates = {}
    if "content" in data:
        updates["content"] = data["content"]
    if "title" in data:
        updates["title"] = data["title"]
    if "status" in data:
        updates["status"] = data["status"]
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        await db.cs_posts.update_one({"post_id": post_id}, {"$set": updates})
    return {"success": True}


@router.delete("/posts/{post_id}")
async def delete_post(post_id: str):
    """Delete a post."""
    result = await db.cs_posts.delete_one({"post_id": post_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"success": True}


@router.post("/posts/{post_id}/infographic")
async def generate_infographic(post_id: str):
    """Generate an infographic for a post using Nano Banana."""
    doc = await db.cs_posts.find_one({"post_id": post_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Post not found")

    content = doc.get("content", doc.get("draft", ""))
    pillar = doc.get("pillar", "enterprise-ai")

    # Generate spec
    spec = await _generate_infographic_spec(content, pillar)

    # Generate image with Nano Banana
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        infographic_chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"cs-img-{uuid.uuid4()}",
            system_message="You are an expert infographic designer. Generate a clean, professional infographic."
        ).with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])

        img_prompt = f"""Generate a professional enterprise infographic.

{spec}

DESIGN: White background, blue (#0066FF) accents, clean typography, no clipart, no cartoons. McKinsey/Stripe quality. Include the title and key data points visually."""

        text_resp, images = await infographic_chat.send_message_multimodal_response(
            UserMessage(text=img_prompt)
        )

        if images and len(images) > 0:
            img_data = images[0]
            import base64
            from pathlib import Path
            filename = f"cs_infographic_{post_id[:8]}.png"
            filepath = Path(__file__).parent.parent / "uploads" / filename
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(img_data))

            await db.cs_posts.update_one({"post_id": post_id}, {"$set": {
                "infographic_path": filename,
                "infographic_spec": spec
            }})

            return {"success": True, "filename": filename, "spec": spec}
        else:
            return {"success": False, "error": "No image generated", "spec": spec}

    except Exception as e:
        logger.error(f"Infographic generation error: {e}")
        return {"success": False, "error": str(e), "spec": spec}


@router.get("/posts/{post_id}/infographic")
async def get_infographic(post_id: str):
    """Get infographic image for a post."""
    from fastapi.responses import FileResponse
    from pathlib import Path
    doc = await db.cs_posts.find_one({"post_id": post_id})
    if not doc or not doc.get("infographic_path"):
        raise HTTPException(status_code=404, detail="No infographic found")

    filepath = Path(__file__).parent.parent / "uploads" / doc["infographic_path"]
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Infographic file not found")
    return FileResponse(str(filepath), media_type="image/png")


# ============== Content Calendar ==============

@router.post("/calendar/generate")
async def generate_calendar(req: CalendarGenerateRequest):
    """Generate a content calendar for N days."""
    if not EMERGENT_KEY:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"cs-cal-{uuid.uuid4()}",
        system_message=f"""You are a content strategist for Vineet Narang.

{ABOUT_ME}

Generate a {req.days}-day content calendar. Each day should have a different pillar and topic.

Available pillars: {json.dumps([p["id"] for p in CONTENT_PILLARS])}

Rules:
- Rotate through pillars evenly
- Mix content types (linkedin-post, carousel, infographic, case-study, framework)
- Each topic should be specific and actionable, not generic
- Include at least 2 "hot take" or contrarian posts per week
- Include 1 case study or architecture deep-dive per week
- Weekend posts can be more personal (lessons, reflections)

Return a JSON array of objects:
[{{"day": 1, "date": "YYYY-MM-DD", "pillar": "pillar-id", "content_type": "type", "topic": "specific topic", "hook_idea": "first line idea"}}]"""
    ).with_model("openai", "gpt-4o")

    start_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    msg = UserMessage(text=f"Generate a {req.days}-day content calendar starting from {start_date}. Make every topic specific and valuable.")
    response = await chat.send_message(msg)

    # Parse response
    try:
        if "```" in response:
            response_clean = response.split("```")[1].replace("json", "").strip()
        else:
            response_clean = response
        calendar_items = json.loads(response_clean)
    except:
        return {"success": False, "error": "Failed to parse calendar", "raw": response}

    # Store calendar items
    for item in calendar_items:
        item["status"] = "scheduled"
        item["created_at"] = datetime.now(timezone.utc)
        await db.cs_calendar.update_one(
            {"date": item.get("date")},
            {"$set": item},
            upsert=True
        )

    return {"success": True, "days": len(calendar_items), "calendar": calendar_items}


@router.get("/calendar")
async def get_calendar(month: Optional[str] = None):
    """Get content calendar."""
    query = {}
    if month:
        query["date"] = {"$regex": f"^{month}"}

    cursor = db.cs_calendar.find(query).sort("date", 1)
    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("created_at"), datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        items.append(doc)

    return {"calendar": items}


# ============== LinkedIn OAuth (Vineet) ==============

cs_oauth_states = {}

@router.get("/oauth/connect")
async def oauth_connect():
    """Start LinkedIn OAuth for Vineet Narang."""
    state = secrets.token_urlsafe(32)
    cs_oauth_states[state] = datetime.now(timezone.utc)

    redirect_uri = CS_LINKEDIN_REDIRECT_URI
    scopes = "openid profile email w_member_social"
    auth_url = (
        f"{LINKEDIN_AUTH_URL}?response_type=code"
        f"&client_id={CS_LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
        f"&scope={scopes}"
    )
    return {"auth_url": auth_url}


@router.get("/oauth/callback")
async def oauth_callback(code: str, state: str):
    """Handle LinkedIn OAuth callback for Vineet."""
    from fastapi.responses import HTMLResponse

    if state not in cs_oauth_states:
        return HTMLResponse("<h1>Invalid state</h1>")

    del cs_oauth_states[state]

    redirect_uri = CS_LINKEDIN_REDIRECT_URI
    async with httpx.AsyncClient() as c:
        token_resp = await c.post(LINKEDIN_TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": CS_LINKEDIN_CLIENT_ID,
            "client_secret": CS_LINKEDIN_CLIENT_SECRET
        })
        if token_resp.status_code != 200:
            return HTMLResponse(f"<h1>Token error: {token_resp.text}</h1>")

        tokens = token_resp.json()
        access_token = tokens.get("access_token")

        # Get user info
        user_resp = await c.get(LINKEDIN_USERINFO_URL, headers={
            "Authorization": f"Bearer {access_token}"
        })
        user_info = user_resp.json() if user_resp.status_code == 200 else {}

    name = user_info.get("name", "Vineet Narang")
    sub = user_info.get("sub", "")

    await db.cs_linkedin_account.update_one(
        {"type": "vineet"},
        {"$set": {
            "access_token": access_token,
            "person_id": sub,
            "name": name,
            "email": user_info.get("email", ""),
            "connected_at": datetime.now(timezone.utc),
            "expires_in": tokens.get("expires_in", 0)
        }},
        upsert=True
    )

    return HTMLResponse(f"""
    <html><body style="font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh;background:#fafafa">
    <div style="text-align:center;padding:40px;background:white;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,0.1)">
    <h2>Connected as {name}</h2>
    <p>You can close this window and return to Content Studio.</p>
    </div></body></html>
    """)


@router.get("/oauth/status")
async def oauth_status():
    """Check LinkedIn connection status for Vineet."""
    account = await db.cs_linkedin_account.find_one({"type": "vineet"})
    if not account or not account.get("access_token"):
        return {"connected": False}
    return {
        "connected": True,
        "name": account.get("name", ""),
        "email": account.get("email", ""),
        "connected_at": account.get("connected_at", "").isoformat() if isinstance(account.get("connected_at"), datetime) else None
    }


@router.post("/publish/{post_id}")
async def publish_to_linkedin(post_id: str, req: PublishRequest):
    """Publish a post to LinkedIn as Vineet Narang."""
    account = await db.cs_linkedin_account.find_one({"type": "vineet"})
    if not account or not account.get("access_token"):
        raise HTTPException(status_code=400, detail="LinkedIn not connected. Please connect via OAuth first.")

    doc = await db.cs_posts.find_one({"post_id": post_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Post not found")

    content = doc.get("content", "")
    if not content:
        raise HTTPException(status_code=400, detail="Post has no content")

    access_token = account["access_token"]
    person_id = account["person_id"]

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": LINKEDIN_API_VERSION
    }

    # Build post payload
    post_payload = {
        "author": f"urn:li:person:{person_id}",
        "commentary": content,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False
    }

    # Upload image if available
    if req.include_image and doc.get("infographic_path"):
        from pathlib import Path
        img_path = Path(__file__).parent.parent / "uploads" / doc["infographic_path"]
        if img_path.exists():
            try:
                async with httpx.AsyncClient() as c:
                    # Initialize upload
                    init_resp = await c.post(
                        "https://api.linkedin.com/rest/images?action=initializeUpload",
                        headers=headers,
                        json={"initializeUploadRequest": {"owner": f"urn:li:person:{person_id}"}}
                    )
                    if init_resp.status_code == 200:
                        upload_data = init_resp.json().get("value", {})
                        upload_url = upload_data.get("uploadUrl", "")
                        image_urn = upload_data.get("image", "")

                        if upload_url:
                            with open(img_path, "rb") as f:
                                img_bytes = f.read()
                            await c.put(upload_url, content=img_bytes, headers={
                                "Authorization": f"Bearer {access_token}",
                                "Content-Type": "image/png"
                            })
                            post_payload["content"] = {
                                "media": {"title": doc.get("title", ""), "id": image_urn}
                            }
            except Exception as e:
                logger.error(f"Image upload failed: {e}")

    # Publish
    async with httpx.AsyncClient() as c:
        resp = await c.post(LINKEDIN_POSTS_URL, headers=headers, json=post_payload)
        if resp.status_code in (200, 201):
            post_urn = resp.headers.get("x-restli-id", "")
            await db.cs_posts.update_one({"post_id": post_id}, {"$set": {
                "status": "published",
                "published_at": datetime.now(timezone.utc),
                "linkedin_urn": post_urn
            }})
            return {"success": True, "urn": post_urn}
        else:
            raise HTTPException(status_code=resp.status_code, detail=f"LinkedIn error: {resp.text[:300]}")
