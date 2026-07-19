import os
import logging
import asyncio
import json
import re
import uuid
import httpx
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/li-search", tags=["linkedin-search"])

mongo_url = os.environ.get('MONGO_URL', '')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'agent_hub')]

EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

VOYAGER_HEADERS = {
    "accept": "application/vnd.linkedin.normalized+json+2.1",
    "x-restli-protocol-version": "2.0.0",
    "x-li-lang": "en_US",
    "x-li-page-instance": "urn:li:page:d_flagship3_search_srp_content;",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

active_searches = {}


class CookieInput(BaseModel):
    li_at: str
    jsessionid: Optional[str] = None


class SearchRequest(BaseModel):
    keywords: List[str]
    date_filter: Optional[str] = "past-month"


class CommentRequest(BaseModel):
    post_urn: str
    comment_text: str


def _build_cookie_header(li_at: str, jsessionid: str = "") -> dict:
    cookie_str = f'li_at={li_at}'
    if jsessionid:
        cookie_str += f'; JSESSIONID="{jsessionid}"'
    headers = {**VOYAGER_HEADERS, "cookie": cookie_str}
    if jsessionid:
        headers["csrf-token"] = jsessionid
    return headers


async def _fetch_linkedin_search(li_at: str, jsessionid: str, keyword: str, start: int = 0, date_filter: str = "past-month") -> dict:
    """Fetch search results from LinkedIn Voyager API."""
    encoded_kw = quote(keyword)
    filters = f"List(resultType->CONTENT,datePosted->{date_filter})"
    url = (
        f"https://www.linkedin.com/voyager/api/search/dash/clusters"
        f"?decorationId=com.linkedin.voyager.dash.deco.search.SearchClusterCollection-191"
        f"&q=all"
        f"&keywords={encoded_kw}"
        f"&filters={filters}"
        f"&origin=GLOBAL_SEARCH_HEADER"
        f"&count=20"
        f"&start={start}"
    )
    headers = _build_cookie_header(li_at, jsessionid)
    async with httpx.AsyncClient(timeout=30) as client_http:
        resp = await client_http.get(url, headers=headers)
        if resp.status_code == 401 or resp.status_code == 403:
            raise HTTPException(status_code=401, detail="LinkedIn session expired. Please update your li_at cookie.")
        if resp.status_code != 200:
            logger.error(f"LinkedIn search failed: {resp.status_code} - {resp.text[:500]}")
            raise HTTPException(status_code=resp.status_code, detail=f"LinkedIn API error: {resp.status_code}")
        return resp.json()


def _parse_search_results(raw_data: dict) -> list:
    """Parse LinkedIn Voyager API response into structured posts."""
    posts = []
    included = raw_data.get("included", [])

    # Build lookup maps for entities
    entity_map = {}
    for item in included:
        eid = item.get("entityUrn") or item.get("$recipeType", "")
        if eid:
            entity_map[eid] = item

    for item in included:
        recipe = item.get("$recipeType", "")

        # Look for update/post items
        if "com.linkedin.voyager.feed.render.UpdateV2" in recipe or "Update" in recipe:
            post = _extract_post_from_update(item, entity_map)
            if post and post.get("text"):
                posts.append(post)
            continue

        # Also check for social detail items that contain commentary
        if item.get("commentary") and item.get("actor"):
            post = _extract_post_from_social(item, entity_map)
            if post and post.get("text"):
                posts.append(post)

    # Deduplicate by post_urn
    seen = set()
    unique = []
    for p in posts:
        urn = p.get("post_urn", "")
        if urn and urn not in seen:
            seen.add(urn)
            unique.append(p)
        elif not urn:
            unique.append(p)

    return unique


def _extract_post_from_update(item: dict, entity_map: dict) -> dict:
    """Extract post data from an UpdateV2 entity."""
    post = {}

    # Get the post URN
    post["post_urn"] = item.get("updateMetadata", {}).get("urn", "") or item.get("entityUrn", "")

    # Extract actor info
    actor = item.get("actor", {})
    if isinstance(actor, dict):
        post["author_name"] = actor.get("name", {}).get("text", "") if isinstance(actor.get("name"), dict) else str(actor.get("name", ""))
        post["author_title"] = actor.get("description", {}).get("text", "") if isinstance(actor.get("description"), dict) else str(actor.get("description", ""))
        nav = actor.get("navigationContext", {})
        post["author_url"] = nav.get("url", "") if isinstance(nav, dict) else ""
    elif isinstance(actor, str) and actor in entity_map:
        actor_data = entity_map[actor]
        post["author_name"] = actor_data.get("name", {}).get("text", "") if isinstance(actor_data.get("name"), dict) else ""
        post["author_title"] = actor_data.get("description", {}).get("text", "") if isinstance(actor_data.get("description"), dict) else ""

    # Extract text content
    commentary = item.get("commentary", {})
    if isinstance(commentary, dict):
        text_obj = commentary.get("text", {})
        post["text"] = text_obj.get("text", "") if isinstance(text_obj, dict) else str(text_obj)
    elif isinstance(commentary, str) and commentary in entity_map:
        ref = entity_map[commentary]
        text_obj = ref.get("text", {})
        post["text"] = text_obj.get("text", "") if isinstance(text_obj, dict) else str(text_obj)
    else:
        post["text"] = ""

    # Extract permalink
    post["post_url"] = ""
    update_meta = item.get("updateMetadata", {})
    if isinstance(update_meta, dict):
        share_url = update_meta.get("shareUrl", "")
        post["post_url"] = share_url

    # Extract timestamp
    post["posted_at"] = None
    if isinstance(actor, dict):
        sub_desc = actor.get("subDescription", {})
        if isinstance(sub_desc, dict):
            post["time_ago"] = sub_desc.get("text", "") if isinstance(sub_desc.get("text"), str) else ""
        else:
            post["time_ago"] = ""
    else:
        post["time_ago"] = ""

    # Social counts
    social = item.get("socialDetail", {})
    if isinstance(social, dict):
        post["likes"] = social.get("totalSocialActivityCounts", {}).get("numLikes", 0) if isinstance(social.get("totalSocialActivityCounts"), dict) else 0
        post["comments_count"] = social.get("totalSocialActivityCounts", {}).get("numComments", 0) if isinstance(social.get("totalSocialActivityCounts"), dict) else 0
    elif isinstance(social, str) and social in entity_map:
        social_data = entity_map[social]
        counts = social_data.get("totalSocialActivityCounts", {})
        post["likes"] = counts.get("numLikes", 0) if isinstance(counts, dict) else 0
        post["comments_count"] = counts.get("numComments", 0) if isinstance(counts, dict) else 0

    return post


def _extract_post_from_social(item: dict, entity_map: dict) -> dict:
    """Fallback extraction from social-type entities."""
    post = {}
    commentary = item.get("commentary", "")
    if isinstance(commentary, dict):
        post["text"] = commentary.get("text", "")
    else:
        post["text"] = str(commentary)

    post["post_urn"] = item.get("entityUrn", "")
    post["author_name"] = ""
    post["author_title"] = ""
    post["author_url"] = ""
    post["post_url"] = ""
    post["time_ago"] = ""
    post["likes"] = 0
    post["comments_count"] = 0
    return post


async def _classify_post(text: str) -> dict:
    """Use AI to classify a LinkedIn post."""
    if not EMERGENT_KEY or not text.strip():
        return {"category": "uncategorized", "relevance": "low", "company_match": "unknown", "summary": text[:200]}

    try:
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"li-classify-{uuid.uuid4()}",
            system_message="""You are a B2B lead classifier. Analyze LinkedIn posts where people are looking for agencies/services.

Classify into these categories:
- "performance_marketing" — looking for performance/growth marketing agency
- "digital_marketing" — looking for digital marketing agency
- "loyalty_rewards" — looking for loyalty, rewards, coupon, cashback agency
- "social_media" — looking for social media marketing agency
- "branding" — looking for branding/creative agency
- "d2c_ecommerce" — looking for D2C, e-commerce solutions
- "tech_development" — looking for tech/app/web development
- "b2b_sales" — looking for B2B sales/lead gen agency
- "general_agency" — looking for general marketing/advertising agency
- "not_relevant" — not looking for any agency/service

Also determine which company should respond:
- "fundle" — for loyalty, rewards, D2C, retail data, mall tech
- "tagandpay" — for performance marketing, digital marketing, social media
- "exceed" — for B2B sales, lead generation
- "any" — could be relevant for multiple
- "none" — not relevant

Respond ONLY in JSON: {"category": "...", "relevance": "high/medium/low", "company_match": "fundle/tagandpay/exceed/any/none", "summary": "1-line summary of what they need"}"""
        ).with_model("openai", "gpt-4o")
        user_msg = UserMessage(text=f"Classify this post:\n\n{text[:1500]}")
        response = await chat.send_message(user_msg)
        resp_text = response.strip()
        # Extract JSON from response
        if "```" in resp_text:
            resp_text = resp_text.split("```")[1].replace("json", "").strip()
        result = json.loads(resp_text)
        return result
    except Exception as e:
        logger.error(f"Classification error: {e}")
        return {"category": "uncategorized", "relevance": "low", "company_match": "unknown", "summary": text[:200]}


# ==================== API Endpoints ====================

@router.post("/cookie")
async def save_cookie(data: CookieInput):
    """Save or update the LinkedIn session cookie."""
    # Verify cookie works by making a test call
    try:
        headers = _build_cookie_header(data.li_at, data.jsessionid or "")
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                "https://www.linkedin.com/voyager/api/me",
                headers=headers
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Cookie validation failed (HTTP {resp.status_code}). Make sure li_at is correct and not expired.")
            me_data = resp.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")

    # Extract profile info
    mini_profile = me_data.get("miniProfile", {})
    first = mini_profile.get("firstName", "")
    last = mini_profile.get("lastName", "")
    occupation = mini_profile.get("occupation", "")

    await db.li_search_config.update_one(
        {"type": "cookie"},
        {"$set": {
            "li_at": data.li_at,
            "jsessionid": data.jsessionid or "",
            "profile_name": f"{first} {last}".strip(),
            "profile_occupation": occupation,
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )

    return {
        "success": True,
        "profile": f"{first} {last}".strip(),
        "occupation": occupation
    }


@router.get("/cookie")
async def get_cookie_status():
    """Check if a valid cookie is stored."""
    config = await db.li_search_config.find_one({"type": "cookie"})
    if not config:
        return {"has_cookie": False}
    return {
        "has_cookie": True,
        "profile_name": config.get("profile_name", ""),
        "profile_occupation": config.get("profile_occupation", ""),
        "updated_at": config.get("updated_at", "").isoformat() if config.get("updated_at") else None
    }


@router.get("/keywords")
async def get_keywords():
    """Get configured search keywords."""
    config = await db.li_search_config.find_one({"type": "keywords"})
    default_keywords = [
        "looking for agency",
        "looking for marketing agency",
        "looking for digital agency",
        "looking for performance marketing agency",
        "need a marketing agency",
        "hiring agency for",
        "looking for loyalty agency",
        "looking for D2C agency",
        "recommend a marketing agency",
        "suggest a digital marketing agency"
    ]
    if not config:
        return {"keywords": default_keywords}
    return {"keywords": config.get("keywords", default_keywords)}


@router.post("/keywords")
async def save_keywords(data: dict):
    """Save search keywords."""
    keywords = data.get("keywords", [])
    if not keywords:
        raise HTTPException(status_code=400, detail="At least one keyword required")
    await db.li_search_config.update_one(
        {"type": "keywords"},
        {"$set": {"keywords": keywords, "updated_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    return {"success": True, "count": len(keywords)}


@router.post("/search")
async def trigger_search(req: Optional[SearchRequest] = None):
    """Trigger a LinkedIn post search."""
    # Get cookie
    config = await db.li_search_config.find_one({"type": "cookie"})
    if not config or not config.get("li_at"):
        raise HTTPException(status_code=400, detail="No LinkedIn cookie configured. Please save your li_at cookie first.")

    li_at = config["li_at"]
    jsessionid = config.get("jsessionid", "")

    # Get keywords
    if req and req.keywords:
        keywords = req.keywords
    else:
        kw_config = await db.li_search_config.find_one({"type": "keywords"})
        keywords = kw_config.get("keywords", ["looking for agency"]) if kw_config else ["looking for agency"]

    date_filter = req.date_filter if req else "past-month"

    # Check if search already running
    if active_searches.get("running"):
        return {"status": "already_running", "message": "A search is already in progress"}

    # Launch background search
    job_id = str(uuid.uuid4())
    active_searches["running"] = True
    active_searches["job_id"] = job_id
    active_searches["progress"] = {"current_keyword": "", "keywords_done": 0, "total_keywords": len(keywords), "posts_found": 0}

    asyncio.create_task(_run_search(job_id, li_at, jsessionid, keywords, date_filter))

    return {"status": "started", "job_id": job_id, "keywords_count": len(keywords)}


async def _run_search(job_id: str, li_at: str, jsessionid: str, keywords: list, date_filter: str):
    """Background search task."""
    total_new = 0
    try:
        for idx, keyword in enumerate(keywords):
            active_searches["progress"]["current_keyword"] = keyword
            active_searches["progress"]["keywords_done"] = idx

            logger.info(f"Searching LinkedIn for: '{keyword}'")
            try:
                all_posts = []
                for page_start in range(0, 60, 20):
                    raw = await _fetch_linkedin_search(li_at, jsessionid, keyword, start=page_start, date_filter=date_filter)
                    parsed = _parse_search_results(raw)
                    all_posts.extend(parsed)
                    if len(parsed) < 5:
                        break
                    await asyncio.sleep(2)

                logger.info(f"  Found {len(all_posts)} posts for '{keyword}'")

                for post in all_posts:
                    # Check if already stored
                    urn = post.get("post_urn", "")
                    if urn:
                        existing = await db.li_search_posts.find_one({"post_urn": urn})
                        if existing:
                            continue

                    # Classify with AI
                    classification = await _classify_post(post.get("text", ""))
                    post.update(classification)
                    post["search_keyword"] = keyword
                    post["found_at"] = datetime.now(timezone.utc)
                    post["status"] = "new"
                    post["commented"] = False

                    await db.li_search_posts.insert_one(post)
                    total_new += 1
                    active_searches["progress"]["posts_found"] = total_new

            except HTTPException:
                logger.error(f"Auth error during search for '{keyword}'")
                break
            except Exception as e:
                logger.error(f"Error searching '{keyword}': {e}")
                continue

            # Rate limit between keywords
            await asyncio.sleep(3)

        active_searches["progress"]["keywords_done"] = len(keywords)

        # Log summary
        await db.li_search_runs.insert_one({
            "job_id": job_id,
            "keywords": keywords,
            "date_filter": date_filter,
            "new_posts_found": total_new,
            "completed_at": datetime.now(timezone.utc)
        })
        logger.info(f"Search complete. {total_new} new posts found.")

    except Exception as e:
        logger.error(f"Search job failed: {e}")
    finally:
        active_searches["running"] = False


@router.get("/search/status")
async def search_status():
    """Get current search progress."""
    running = active_searches.get("running", False)
    progress = active_searches.get("progress", {})
    return {
        "running": running,
        "job_id": active_searches.get("job_id"),
        **progress
    }


@router.get("/posts")
async def get_posts(
    category: Optional[str] = None,
    company_match: Optional[str] = None,
    relevance: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    sort: str = "found_at"
):
    """Get discovered posts with filters."""
    query = {}
    if category and category != "all":
        query["category"] = category
    if company_match and company_match != "all":
        query["company_match"] = company_match
    if relevance and relevance != "all":
        query["relevance"] = relevance
    if status and status != "all":
        query["status"] = status

    # Exclude not_relevant by default unless specifically requested
    if "category" not in query:
        query["category"] = {"$ne": "not_relevant"}

    total = await db.li_search_posts.count_documents(query)
    cursor = db.li_search_posts.find(query).sort(sort, -1).skip(skip).limit(limit)
    posts = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("found_at"), datetime):
            doc["found_at"] = doc["found_at"].isoformat()
        posts.append(doc)

    # Stats
    total_all = await db.li_search_posts.count_documents({})
    high_rel = await db.li_search_posts.count_documents({"relevance": "high"})
    commented = await db.li_search_posts.count_documents({"commented": True})

    return {
        "posts": posts,
        "total": total,
        "stats": {
            "total_posts": total_all,
            "high_relevance": high_rel,
            "commented": commented
        }
    }


@router.post("/posts/{post_id}/classify")
async def reclassify_post(post_id: str):
    """Re-classify a specific post."""
    from bson import ObjectId
    doc = await db.li_search_posts.find_one({"_id": ObjectId(post_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Post not found")

    classification = await _classify_post(doc.get("text", ""))
    await db.li_search_posts.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": classification}
    )
    return {"success": True, **classification}


@router.post("/posts/{post_id}/comment")
async def comment_on_post(post_id: str, data: CommentRequest):
    """Post a comment on a LinkedIn post."""
    from bson import ObjectId
    config = await db.li_search_config.find_one({"type": "cookie"})
    if not config or not config.get("li_at"):
        raise HTTPException(status_code=400, detail="No LinkedIn cookie configured")

    doc = await db.li_search_posts.find_one({"_id": ObjectId(post_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Post not found")

    li_at = config["li_at"]
    jsessionid = config.get("jsessionid", "")
    headers = _build_cookie_header(li_at, jsessionid)
    headers["content-type"] = "application/json"

    # The post URN for commenting
    post_urn = data.post_urn or doc.get("post_urn", "")
    if not post_urn:
        raise HTTPException(status_code=400, detail="No post URN available for commenting")

    # LinkedIn comment API
    comment_payload = {
        "commentary": data.comment_text,
    }

    comment_url = f"https://www.linkedin.com/voyager/api/feed/comments"
    comment_body = {
        "threadUrn": post_urn,
        "comment": {
            "values": [{
                "com.linkedin.voyager.feed.MemberComment": {
                    "values": [{"value": data.comment_text}]
                }
            }]
        }
    }

    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(comment_url, headers=headers, json=comment_body)
            if resp.status_code in (200, 201):
                await db.li_search_posts.update_one(
                    {"_id": ObjectId(post_id)},
                    {"$set": {
                        "commented": True,
                        "comment_text": data.comment_text,
                        "commented_at": datetime.now(timezone.utc),
                        "status": "commented"
                    }}
                )
                return {"success": True, "message": "Comment posted"}
            else:
                logger.error(f"Comment failed: {resp.status_code} - {resp.text[:500]}")
                return {"success": False, "error": f"LinkedIn returned {resp.status_code}", "detail": resp.text[:300]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/posts/{post_id}/generate-comment")
async def generate_comment(post_id: str, data: dict):
    """AI-generate a comment for a post."""
    from bson import ObjectId
    doc = await db.li_search_posts.find_one({"_id": ObjectId(post_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Post not found")

    company = data.get("company", doc.get("company_match", "fundle"))
    company_contexts = {
        "fundle": "Fundle.ai — a Retail Intelligence Platform powering malls, brands, and consumers through unified data, AI insights, loyalty, rewards, and D2C engagement.",
        "tagandpay": "TagandPay — a performance marketing and digital growth agency specializing in D2C brands, social media, and customer acquisition.",
        "exceed": "Exceed Agents — a B2B sales acceleration platform with AI-powered outreach, lead generation, and pipeline management.",
    }
    context = company_contexts.get(company, company_contexts["fundle"])

    try:
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"li-comment-{uuid.uuid4()}",
            system_message=f"""You write LinkedIn comments that are helpful, professional, and subtly introduce your company without being salesy.

Your company: {context}

Guidelines:
- Start by acknowledging what the poster is looking for
- Share a brief, relevant insight or tip
- Naturally mention your company as a potential fit
- Keep it under 100 words
- Be conversational, not corporate
- Don't use hashtags
- End with an open invitation to connect/chat"""
        ).with_model("openai", "gpt-4o")
        user_msg = UserMessage(text=f"Write a comment for this LinkedIn post:\n\n{doc.get('text', '')[:1500]}")
        response = await chat.send_message(user_msg)
        return {"success": True, "comment": response.strip()}
    except Exception as e:
        logger.error(f"Comment generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/posts/{post_id}")
async def delete_post(post_id: str):
    """Remove a post from results."""
    from bson import ObjectId
    result = await db.li_search_posts.delete_one({"_id": ObjectId(post_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"success": True}


@router.get("/runs")
async def get_search_runs():
    """Get history of search runs."""
    cursor = db.li_search_runs.find().sort("completed_at", -1).limit(20)
    runs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("completed_at"), datetime):
            doc["completed_at"] = doc["completed_at"].isoformat()
        runs.append(doc)
    return {"runs": runs}


# ==================== MESSAGING ENDPOINTS ====================

class MessageRequest(BaseModel):
    recipient_urn: str
    message_text: str


class BulkMessageRequest(BaseModel):
    recipient_urns: List[str]
    message_text: str


async def _fetch_connections(li_at: str, jsessionid: str, start: int = 0, count: int = 40, keyword: str = "") -> dict:
    """Fetch 1st-degree connections from LinkedIn."""
    headers = _build_cookie_header(li_at, jsessionid)
    params = {
        "decorationId": "com.linkedin.voyager.dash.deco.web.mynetwork.ConnectionListWithProfile-16",
        "count": str(count),
        "q": "search",
        "sortType": "RECENTLY_ADDED",
        "start": str(start),
    }
    if keyword:
        params["keywords"] = keyword

    url = "https://www.linkedin.com/voyager/api/relationships/dash/connections"
    async with httpx.AsyncClient(timeout=20) as c:
        resp = await c.get(url, headers=headers, params=params)
        if resp.status_code == 401 or resp.status_code == 403:
            raise HTTPException(status_code=401, detail="LinkedIn session expired. Please update your li_at cookie.")
        if resp.status_code != 200:
            logger.error(f"Connections fetch failed: {resp.status_code} - {resp.text[:500]}")
            raise HTTPException(status_code=resp.status_code, detail=f"LinkedIn API error: {resp.status_code}")
        return resp.json()


def _parse_connections(raw_data: dict) -> list:
    """Parse connections response into structured list."""
    connections = []
    included = raw_data.get("included", [])
    paging = raw_data.get("data", {}).get("paging", {}) or {}

    # Build entity lookup
    profiles = {}
    for item in included:
        recipe = item.get("$recipeType", "")
        urn = item.get("entityUrn", "")

        if "MiniProfile" in recipe or "com.linkedin.voyager.identity.shared.MiniProfile" in recipe:
            profiles[urn] = {
                "urn": urn,
                "first_name": item.get("firstName", ""),
                "last_name": item.get("lastName", ""),
                "occupation": item.get("occupation", ""),
                "public_id": item.get("publicIdentifier", ""),
                "profile_url": f"https://www.linkedin.com/in/{item.get('publicIdentifier', '')}",
            }
            # Try to get profile picture
            picture = item.get("picture", {})
            if isinstance(picture, dict):
                artifacts = picture.get("com.linkedin.common.VectorImage", {}).get("artifacts", [])
                if artifacts:
                    root = picture.get("com.linkedin.common.VectorImage", {}).get("rootUrl", "")
                    smallest = artifacts[0].get("fileIdentifyingUrlPathSegment", "")
                    profiles[urn]["avatar_url"] = root + smallest if root else ""
                else:
                    profiles[urn]["avatar_url"] = ""
            else:
                profiles[urn]["avatar_url"] = ""

    # Match connections to profiles
    for item in included:
        recipe = item.get("$recipeType", "")
        if "Connection" in recipe:
            created = item.get("createdAt", 0)
            # Find the linked profile
            member_ref = item.get("connectedMemberResolutionResult", "")
            if isinstance(member_ref, str) and member_ref in profiles:
                conn = {**profiles[member_ref]}
                conn["connected_at"] = datetime.fromtimestamp(created / 1000, tz=timezone.utc).isoformat() if created else None
                connections.append(conn)
            elif isinstance(member_ref, dict):
                urn = member_ref.get("entityUrn", "")
                if urn in profiles:
                    conn = {**profiles[urn]}
                    conn["connected_at"] = datetime.fromtimestamp(created / 1000, tz=timezone.utc).isoformat() if created else None
                    connections.append(conn)

    # If no connection-type entities found, just return all profiles
    if not connections and profiles:
        connections = list(profiles.values())

    return connections, paging


async def _send_linkedin_message(li_at: str, jsessionid: str, recipient_urn: str, message_text: str) -> dict:
    """Send a message to a LinkedIn connection."""
    headers = _build_cookie_header(li_at, jsessionid)
    headers["content-type"] = "application/json"
    headers["accept"] = "application/vnd.linkedin.normalized+json+2.1"

    # Clean the URN - we need the fsd_profile format
    # recipient_urn might be like "urn:li:fsd_profile:ACoAAXXX" or "urn:li:member:12345"
    clean_urn = recipient_urn
    if "miniProfile" in recipient_urn:
        # Convert miniProfile URN to fsd_profile
        clean_urn = recipient_urn.replace("fs_miniProfile", "fsd_profile")

    payload = {
        "conversationCreate": {
            "eventCreate": {
                "value": {
                    "com.linkedin.voyager.messaging.create.MessageCreate": {
                        "attributedBody": {
                            "text": message_text,
                            "attributes": []
                        }
                    }
                }
            },
            "recipients": [clean_urn],
            "subtype": "MEMBER_TO_MEMBER"
        }
    }

    url = "https://www.linkedin.com/voyager/api/messaging/conversations?action=create"
    async with httpx.AsyncClient(timeout=15) as c:
        resp = await c.post(url, headers=headers, json=payload)
        if resp.status_code in (200, 201):
            return {"success": True}
        elif resp.status_code == 401 or resp.status_code == 403:
            raise HTTPException(status_code=401, detail="LinkedIn session expired")
        else:
            logger.error(f"Message send failed: {resp.status_code} - {resp.text[:500]}")
            return {"success": False, "error": f"HTTP {resp.status_code}", "detail": resp.text[:300]}


@router.get("/connections")
async def get_connections(
    start: int = 0,
    count: int = 40,
    keyword: str = ""
):
    """Fetch 1st-degree LinkedIn connections."""
    config = await db.li_search_config.find_one({"type": "cookie"})
    if not config or not config.get("li_at"):
        raise HTTPException(status_code=400, detail="No LinkedIn cookie configured")

    raw = await _fetch_connections(config["li_at"], config.get("jsessionid", ""), start, count, keyword)
    connections, paging = _parse_connections(raw)

    return {
        "connections": connections,
        "total": paging.get("total", len(connections)),
        "start": start,
        "count": count
    }


@router.post("/message/send")
async def send_message(data: MessageRequest):
    """Send a message to a single connection."""
    config = await db.li_search_config.find_one({"type": "cookie"})
    if not config or not config.get("li_at"):
        raise HTTPException(status_code=400, detail="No LinkedIn cookie configured")

    result = await _send_linkedin_message(
        config["li_at"], config.get("jsessionid", ""),
        data.recipient_urn, data.message_text
    )

    if result.get("success"):
        # Log the message
        await db.li_messages_log.insert_one({
            "recipient_urn": data.recipient_urn,
            "message_text": data.message_text,
            "sent_at": datetime.now(timezone.utc),
            "status": "sent"
        })

    return result


@router.post("/message/bulk")
async def send_bulk_messages(data: BulkMessageRequest):
    """Send a message to multiple connections."""
    config = await db.li_search_config.find_one({"type": "cookie"})
    if not config or not config.get("li_at"):
        raise HTTPException(status_code=400, detail="No LinkedIn cookie configured")

    results = {"sent": 0, "failed": 0, "errors": []}

    for urn in data.recipient_urns:
        try:
            result = await _send_linkedin_message(
                config["li_at"], config.get("jsessionid", ""),
                urn, data.message_text
            )
            if result.get("success"):
                results["sent"] += 1
                await db.li_messages_log.insert_one({
                    "recipient_urn": urn,
                    "message_text": data.message_text,
                    "sent_at": datetime.now(timezone.utc),
                    "status": "sent"
                })
            else:
                results["failed"] += 1
                results["errors"].append({"urn": urn, "error": result.get("error", "Unknown")})
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"urn": urn, "error": str(e)})

        # Rate limit: 3-5 seconds between messages
        await asyncio.sleep(4)

    return results


@router.post("/message/generate")
async def generate_message(data: dict):
    """AI-generate a personalized message for a connection."""
    recipient_name = data.get("recipient_name", "")
    recipient_title = data.get("recipient_title", "")
    purpose = data.get("purpose", "introduce services")
    company = data.get("company", "fundle")

    company_contexts = {
        "fundle": "Fundle.ai — a Retail Intelligence Platform powering malls, brands, and consumers through unified data, AI insights, loyalty, rewards, and D2C engagement.",
        "tagandpay": "TagandPay — a performance marketing and digital growth agency specializing in D2C brands, social media, and customer acquisition.",
        "exceed": "Exceed Agents — a B2B sales acceleration platform with AI-powered outreach, lead generation, and pipeline management.",
    }
    context = company_contexts.get(company, company_contexts["fundle"])

    try:
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"li-msg-{uuid.uuid4()}",
            system_message=f"""You write short, professional LinkedIn messages.

Your company: {context}

Guidelines:
- Keep it under 80 words — LinkedIn messages should be brief
- Be warm and personal, not corporate
- Reference their role/company if known
- Clearly state why you're reaching out
- Include a soft CTA (quick call, coffee chat, etc.)
- NO hashtags, NO emojis, NO formal salutations like "Dear"
- Start with "Hi [Name]," format"""
        ).with_model("openai", "gpt-4o")
        prompt = f"Write a LinkedIn message to {recipient_name}"
        if recipient_title:
            prompt += f" ({recipient_title})"
        prompt += f". Purpose: {purpose}"

        user_msg = UserMessage(text=prompt)
        response = await chat.send_message(user_msg)
        return {"success": True, "message": response.strip()}
    except Exception as e:
        logger.error(f"Message generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages/log")
async def get_message_log(skip: int = 0, limit: int = 50):
    """Get sent messages log."""
    total = await db.li_messages_log.count_documents({})
    cursor = db.li_messages_log.find().sort("sent_at", -1).skip(skip).limit(limit)
    messages = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("sent_at"), datetime):
            doc["sent_at"] = doc["sent_at"].isoformat()
        messages.append(doc)
    return {"messages": messages, "total": total}
