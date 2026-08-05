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
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "accept-language": "en-US,en;q=0.9",
    "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

active_searches = {}


class CookieInput(BaseModel):
    li_at: str
    jsessionid: Optional[str] = None


class SearchRequest(BaseModel):
    keywords: Optional[List[str]] = None
    date_filter: Optional[str] = "past-month"


class CommentRequest(BaseModel):
    post_urn: str
    comment_text: str


def _build_cookie_header(li_at: str, jsessionid: str = "") -> dict:
    cookie_str = f'li_at={li_at}'
    if jsessionid:
        clean_jsession = jsessionid.strip('"')
        cookie_str += f'; JSESSIONID="{clean_jsession}"'
    headers = {**VOYAGER_HEADERS, "cookie": cookie_str}
    if jsessionid:
        clean_jsession = jsessionid.strip('"')
        headers["csrf-token"] = clean_jsession
    return headers


async def _obtain_jsessionid(li_at: str) -> str:
    """Obtain a JSESSIONID cookie from LinkedIn."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            # Step 1: Hit homepage to get a base JSESSIONID
            homepage_resp = await c.get(
                "https://www.linkedin.com/",
                headers={
                    "user-agent": VOYAGER_HEADERS["user-agent"],
                    "accept": "text/html,application/xhtml+xml",
                    "accept-language": "en-US,en;q=0.9",
                },
            )
            jsessionid = ""
            for cookie_header in homepage_resp.headers.get_list("set-cookie"):
                if "JSESSIONID" in cookie_header:
                    parts = cookie_header.split(";")[0]
                    if "=" in parts:
                        jsessionid = parts.split("=", 1)[1].strip('"')
                        logger.info(f"Obtained JSESSIONID from homepage: {jsessionid[:30]}...")
                        break

            if not jsessionid:
                # Try /feed with the li_at cookie  
                feed_resp = await c.get(
                    "https://www.linkedin.com/feed/",
                    headers={
                        "cookie": f"li_at={li_at}",
                        "user-agent": VOYAGER_HEADERS["user-agent"],
                        "accept": "text/html,application/xhtml+xml",
                    },
                )
                for cookie_header in feed_resp.headers.get_list("set-cookie"):
                    if "JSESSIONID" in cookie_header:
                        parts = cookie_header.split(";")[0]
                        if "=" in parts:
                            jsessionid = parts.split("=", 1)[1].strip('"')
                            logger.info(f"Obtained JSESSIONID from feed: {jsessionid[:30]}...")
                            break

            return jsessionid
    except Exception as e:
        logger.error(f"Failed to obtain JSESSIONID: {e}")
    return ""


async def _ensure_jsessionid(li_at: str, jsessionid: str) -> str:
    """Ensure we have a JSESSIONID. Auto-obtain if missing and persist to DB."""
    if jsessionid:
        return jsessionid
    jsessionid = await _obtain_jsessionid(li_at)
    if jsessionid:
        await db.li_search_config.update_one(
            {"type": "cookie"},
            {"$set": {"jsessionid": jsessionid}}
        )
    return jsessionid


async def _playwright_search(li_at: str, keyword: str, max_results: int = 20) -> list:
    """Use Playwright with injected li_at cookie to search LinkedIn posts."""
    from playwright.async_api import async_playwright

    posts = []
    encoded_kw = quote(keyword)
    search_url = f"https://www.linkedin.com/search/results/content/?keywords={encoded_kw}&origin=GLOBAL_SEARCH_HEADER"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=VOYAGER_HEADERS["user-agent"],
            )
            # Inject li_at cookie
            await context.add_cookies([{
                "name": "li_at",
                "value": li_at,
                "domain": ".linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
                "sameSite": "None",
            }])

            page = await context.new_page()
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # Check if we got redirected to login
            if "/login" in page.url or "/checkpoint" in page.url:
                logger.error(f"Playwright: Redirected to {page.url} — cookie not accepted")
                await browser.close()
                return []

            # Scroll to load more results
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1500)")
                await page.wait_for_timeout(1500)

            # Extract posts from the page
            posts = await page.evaluate("""
                () => {
                    const results = [];
                    const feedItems = document.querySelectorAll('.feed-shared-update-v2');
                    
                    feedItems.forEach((item) => {
                        try {
                            // Author info
                            const actorEl = item.querySelector('.update-components-actor__title span[aria-hidden="true"]');
                            const authorName = actorEl ? actorEl.innerText.trim() : '';
                            
                            const descEl = item.querySelector('.update-components-actor__description span[aria-hidden="true"]');
                            const authorTitle = descEl ? descEl.innerText.trim() : '';
                            
                            // Post text
                            const textEl = item.querySelector('.feed-shared-update-v2__description, .update-components-text, .feed-shared-text');
                            const text = textEl ? textEl.innerText.trim() : '';
                            
                            // Post URL
                            const linkEl = item.querySelector('a[href*="/posts/"], a[href*="/feed/update/"]');
                            const postUrl = linkEl ? linkEl.href : '';
                            
                            // Time
                            const timeEl = item.querySelector('.update-components-actor__sub-description span[aria-hidden="true"]');
                            const timeAgo = timeEl ? timeEl.innerText.trim() : '';
                            
                            // Social counts
                            const likesEl = item.querySelector('.social-details-social-counts__reactions-count');
                            const likes = likesEl ? parseInt(likesEl.innerText.replace(/[^0-9]/g, '')) || 0 : 0;
                            
                            const commentsEl = item.querySelector('.social-details-social-counts__comments');
                            const commentsCount = commentsEl ? parseInt(commentsEl.innerText.replace(/[^0-9]/g, '')) || 0 : 0;
                            
                            // URN from data attribute
                            const urn = item.getAttribute('data-urn') || '';
                            
                            if (text.length > 20) {
                                results.push({
                                    author_name: authorName,
                                    author_title: authorTitle,
                                    text: text,
                                    post_url: postUrl,
                                    time_ago: timeAgo,
                                    likes: likes,
                                    comments_count: commentsCount,
                                    post_urn: urn
                                });
                            }
                        } catch(e) {}
                    });
                    
                    // Fallback: try broader selectors if feed-shared-update-v2 didn't work
                    if (results.length === 0) {
                        const searchItems = document.querySelectorAll('[data-chameleon-result-urn], .reusable-search__result-container');
                        searchItems.forEach((item) => {
                            try {
                                const text = item.innerText || '';
                                const links = Array.from(item.querySelectorAll('a[href*="linkedin.com"]'));
                                const postUrl = links.length > 0 ? links[0].href : '';
                                const urn = item.getAttribute('data-chameleon-result-urn') || '';
                                if (text.length > 50) {
                                    // Try to split author from content
                                    const lines = text.split('\\n').filter(l => l.trim());
                                    results.push({
                                        author_name: lines[0] || '',
                                        author_title: lines[1] || '',
                                        text: lines.slice(2).join('\\n').trim() || text.substring(0, 500),
                                        post_url: postUrl,
                                        time_ago: '',
                                        likes: 0,
                                        comments_count: 0,
                                        post_urn: urn
                                    });
                                }
                            } catch(e) {}
                        });
                    }
                    
                    return results;
                }
            """)

            logger.info(f"Playwright search for '{keyword}': found {len(posts)} posts")
            await browser.close()

    except Exception as e:
        logger.error(f"Playwright search error: {e}")

    return posts[:max_results]


async def _playwright_connections(li_at: str, keyword: str = "") -> list:
    """Use Playwright with injected li_at cookie to fetch connections."""
    from playwright.async_api import async_playwright

    connections = []
    url = "https://www.linkedin.com/mynetwork/invite-connect/connections/"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=VOYAGER_HEADERS["user-agent"],
            )
            await context.add_cookies([{
                "name": "li_at",
                "value": li_at,
                "domain": ".linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
                "sameSite": "None",
            }])

            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            if "/login" in page.url or "/checkpoint" in page.url:
                logger.error(f"Playwright connections: Redirected to login")
                await browser.close()
                return []

            # Search filter if keyword
            if keyword:
                try:
                    search_input = page.locator('input[placeholder*="Search"]').first
                    if await search_input.is_visible(timeout=3000):
                        await search_input.fill(keyword)
                        await page.wait_for_timeout(2000)
                except:
                    pass

            # Scroll to load connections
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1500)")
                await page.wait_for_timeout(1500)

            # Extract connections
            connections = await page.evaluate("""
                () => {
                    const results = [];
                    const cards = document.querySelectorAll('.mn-connection-card, .scaffold-finite-scroll__content li');
                    
                    cards.forEach((card) => {
                        try {
                            const nameEl = card.querySelector('.mn-connection-card__name, .entity-result__title-text a span[aria-hidden="true"]');
                            const name = nameEl ? nameEl.innerText.trim() : '';
                            
                            const occEl = card.querySelector('.mn-connection-card__occupation, .entity-result__primary-subtitle');
                            const occupation = occEl ? occEl.innerText.trim() : '';
                            
                            const linkEl = card.querySelector('a[href*="/in/"]');
                            const profileUrl = linkEl ? linkEl.href : '';
                            const publicId = profileUrl ? profileUrl.split('/in/')[1]?.split('/')[0]?.split('?')[0] : '';
                            
                            const imgEl = card.querySelector('img.presence-entity__image, img.EntityPhoto-circle-4');
                            const avatarUrl = imgEl ? imgEl.src : '';
                            
                            if (name) {
                                const nameParts = name.split(' ');
                                results.push({
                                    first_name: nameParts[0] || '',
                                    last_name: nameParts.slice(1).join(' ') || '',
                                    occupation: occupation,
                                    public_id: publicId,
                                    profile_url: profileUrl,
                                    avatar_url: avatarUrl,
                                    urn: 'urn:li:fsd_profile:' + publicId,
                                });
                            }
                        } catch(e) {}
                    });
                    
                    return results;
                }
            """)

            logger.info(f"Playwright connections: found {len(connections)}")
            await browser.close()

    except Exception as e:
        logger.error(f"Playwright connections error: {e}")

    return connections


async def _fetch_linkedin_search(li_at: str, jsessionid: str, keyword: str, start: int = 0, date_filter: str = "past-month") -> dict:
    """Fetch search results from LinkedIn Voyager API."""
    jsessionid = await _ensure_jsessionid(li_at, jsessionid)
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
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client_http:
        resp = await client_http.get(url, headers=headers)
        logger.info(f"Search API response: HTTP {resp.status_code} for '{keyword}'")
        if resp.status_code == 302:
            logger.error(f"LinkedIn redirected — cookie not accepted. Redirect to: {resp.headers.get('location', 'unknown')}")
            raise HTTPException(status_code=401, detail="LinkedIn cookie not accepted from this server. The li_at cookie may be IP-bound to your browser session.")
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
    li_at = data.li_at.strip()
    jsessionid = (data.jsessionid or "").strip().strip('"')

    # Step 1: If no JSESSIONID provided, obtain one automatically
    if not jsessionid:
        logger.info("No JSESSIONID provided, obtaining automatically...")
        jsessionid = await _obtain_jsessionid(li_at)

    # Step 2: Validate the cookie by calling Voyager API
    headers = _build_cookie_header(li_at, jsessionid)
    me_data = None
    validation_error = None

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as c:
            resp = await c.get(
                "https://www.linkedin.com/voyager/api/me",
                headers=headers
            )
            logger.info(f"Cookie validation response: HTTP {resp.status_code}")

            if resp.status_code == 200:
                me_data = resp.json()
            elif resp.status_code in (302, 303):
                validation_error = "LinkedIn redirected to login — cookie may be expired or invalid."
            elif resp.status_code == 403:
                # CSRF issue — try without csrf-token header but with cookie
                logger.info("Got 403, trying alternate validation...")
                alt_headers = {
                    "cookie": f"li_at={li_at}",
                    "user-agent": VOYAGER_HEADERS["user-agent"],
                    "accept": "text/html",
                }
                alt_resp = await c.get("https://www.linkedin.com/feed/", headers=alt_headers)
                if alt_resp.status_code == 200 or (alt_resp.status_code == 302 and "feed" in alt_resp.headers.get("location", "")):
                    # Cookie is valid but JSESSIONID is wrong/missing — extract new one
                    for cookie_header in alt_resp.headers.get_list("set-cookie"):
                        if "JSESSIONID" in cookie_header:
                            parts = cookie_header.split(";")[0]
                            if "=" in parts:
                                jsessionid = parts.split("=", 1)[1].strip('"')
                                logger.info(f"Got new JSESSIONID from feed: {jsessionid[:20]}...")
                    # Retry Voyager with new JSESSIONID
                    if jsessionid:
                        retry_headers = _build_cookie_header(li_at, jsessionid)
                        retry_resp = await c.get(
                            "https://www.linkedin.com/voyager/api/me",
                            headers=retry_headers
                        )
                        if retry_resp.status_code == 200:
                            me_data = retry_resp.json()
                        else:
                            validation_error = f"Voyager API returned {retry_resp.status_code} after JSESSIONID refresh."
                    else:
                        validation_error = "Could not obtain JSESSIONID. Cookie may be invalid."
                else:
                    validation_error = f"LinkedIn rejected the cookie (feed returned {alt_resp.status_code})."
            elif resp.status_code == 401:
                validation_error = "Cookie is expired or invalid (401 Unauthorized)."
            else:
                validation_error = f"Unexpected response from LinkedIn (HTTP {resp.status_code})."
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Network error connecting to LinkedIn: {str(e)}")

    if validation_error and not me_data:
        # Even if Voyager /me fails, let's try one more thing — just save and let the user test
        # Some cookies work for search but /me returns errors
        logger.warning(f"Cookie validation issue: {validation_error}")

        # Try a simpler validation: just check if LinkedIn recognizes us
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
                check_resp = await c.get(
                    "https://www.linkedin.com/voyager/api/identity/profiles/me/profileView",
                    headers=_build_cookie_header(li_at, jsessionid)
                )
                if check_resp.status_code == 200:
                    me_data = check_resp.json()
                    logger.info("Alternate profile endpoint worked!")
        except:
            pass

    # If still no me_data, save anyway with a warning (user says it's a live cookie)
    if not me_data:
        # Save the cookie anyway but flag it
        await db.li_search_config.update_one(
            {"type": "cookie"},
            {"$set": {
                "li_at": li_at,
                "jsessionid": jsessionid,
                "profile_name": "LinkedIn User",
                "profile_occupation": "",
                "updated_at": datetime.now(timezone.utc),
                "validation_warning": validation_error
            }},
            upsert=True
        )
        return {
            "success": True,
            "profile": "LinkedIn User (validation skipped)",
            "occupation": "",
            "warning": "Cookie saved. Full validation could not be completed — try running a search to verify it works."
        }

    # Extract profile info
    mini_profile = me_data.get("miniProfile", me_data.get("profile", {}))
    if not isinstance(mini_profile, dict):
        mini_profile = {}
    first = mini_profile.get("firstName", "")
    last = mini_profile.get("lastName", "")
    occupation = mini_profile.get("occupation", "")

    # Fallback: check included array
    if not first and "included" in me_data:
        for item in me_data.get("included", []):
            if item.get("firstName"):
                first = item.get("firstName", "")
                last = item.get("lastName", "")
                occupation = item.get("occupation", "")
                break

    name = f"{first} {last}".strip() or "LinkedIn User"

    await db.li_search_config.update_one(
        {"type": "cookie"},
        {"$set": {
            "li_at": li_at,
            "jsessionid": jsessionid,
            "profile_name": name,
            "profile_occupation": occupation,
            "updated_at": datetime.now(timezone.utc),
            "validation_warning": None
        }},
        upsert=True
    )

    return {
        "success": True,
        "profile": name,
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
    """Trigger a LinkedIn post search. Note: Due to LinkedIn's anti-bot measures, 
    server-side search uses web search indexing. The li_at cookie is used for 
    messaging and commenting only."""
    # Get keywords
    if req and req.keywords:
        keywords = req.keywords
    else:
        kw_config = await db.li_search_config.find_one({"type": "keywords"})
        keywords = kw_config.get("keywords", ["looking for agency"]) if kw_config else ["looking for agency"]

    # Check if search already running
    if active_searches.get("running"):
        return {"status": "already_running", "message": "A search is already in progress"}

    # Launch background search
    job_id = str(uuid.uuid4())
    active_searches["running"] = True
    active_searches["job_id"] = job_id
    active_searches["progress"] = {"current_keyword": "", "keywords_done": 0, "total_keywords": len(keywords), "posts_found": 0}

    # Get cookie if available (for Playwright fallback)
    config = await db.li_search_config.find_one({"type": "cookie"})
    li_at = config.get("li_at", "") if config else ""
    jsessionid = config.get("jsessionid", "") if config else ""

    asyncio.create_task(_run_search(job_id, li_at, jsessionid, keywords, "past-month"))

    return {"status": "started", "job_id": job_id, "keywords_count": len(keywords)}


async def _run_search(job_id: str, li_at: str, jsessionid: str, keywords: list, date_filter: str):
    """Background search task — uses Playwright (primary) with API fallback."""
    total_new = 0
    try:
        for idx, keyword in enumerate(keywords):
            active_searches["progress"]["current_keyword"] = keyword
            active_searches["progress"]["keywords_done"] = idx

            logger.info(f"Searching LinkedIn for: '{keyword}' (Playwright)")
            try:
                # Primary: Playwright-based search
                all_posts = await _playwright_search(li_at, keyword, max_results=20)

                # Fallback: Try Voyager API if Playwright found nothing
                if not all_posts:
                    logger.info(f"  Playwright found 0 posts, trying Voyager API fallback...")
                    try:
                        raw = await _fetch_linkedin_search(li_at, jsessionid, keyword, start=0, date_filter=date_filter)
                        all_posts = _parse_search_results(raw)
                    except Exception as api_err:
                        logger.warning(f"  API fallback also failed: {api_err}")

                logger.info(f"  Found {len(all_posts)} posts for '{keyword}'")

                for post in all_posts:
                    # Deduplicate by text content hash or URN
                    urn = post.get("post_urn", "")
                    text = post.get("text", "")
                    if urn:
                        existing = await db.li_search_posts.find_one({"post_urn": urn})
                        if existing:
                            continue
                    elif text:
                        # Check by text similarity (first 100 chars)
                        existing = await db.li_search_posts.find_one({"text": {"$regex": f"^{re.escape(text[:100])}"}})
                        if existing:
                            continue

                    # Classify with AI
                    classification = await _classify_post(text)
                    post.update(classification)
                    post["search_keyword"] = keyword
                    post["found_at"] = datetime.now(timezone.utc)
                    post["status"] = "new"
                    post["commented"] = False

                    await db.li_search_posts.insert_one(post)
                    total_new += 1
                    active_searches["progress"]["posts_found"] = total_new

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
    jsessionid = await _ensure_jsessionid(li_at, jsessionid)
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
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as c:
        resp = await c.get(url, headers=headers, params=params)
        logger.info(f"Connections API response: HTTP {resp.status_code}")
        if resp.status_code == 302:
            raise HTTPException(status_code=401, detail="LinkedIn cookie not accepted. Please update your li_at cookie — it may be IP-bound to your browser.")
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


@router.post("/message/script")
async def generate_message_script(data: dict):
    """Generate a browser script that looks up URNs via search and sends messages in bulk."""
    recipients = data.get("recipients", [])
    message = data.get("message", "")
    if not recipients or not message:
        raise HTTPException(status_code=400, detail="Recipients and message required")

    message_js = json.dumps(message)
    recipients_js = json.dumps(recipients)

    script = (
        "// === LinkedIn Bulk Messenger v7 ===\n"
        "// Verbose logging to debug URN lookup\n\n"
        "(async () => {\n"
        "  const recipients = " + recipients_js + ";\n"
        "  const message = " + message_js + ";\n"
        "  let sent = 0, failed = 0, skipped = 0;\n"
        "  const delay = ms => new Promise(r => setTimeout(r, ms));\n"
        "  const csrf = (document.cookie.match(/JSESSIONID=\"?([^;\"]+)/) || [])[1] || '';\n"
        "  if (!csrf) { alert('Not logged in'); return; }\n\n"
        "  console.log('=== Bulk Messenger v7: ' + recipients.length + ' recipients ===');\n\n"
        "  for (let i = 0; i < recipients.length; i++) {\n"
        "    const rec = recipients[i];\n"
        "    console.log('(' + (i+1) + '/' + recipients.length + ') ' + rec.name);\n"
        "    console.log('  public_id=' + rec.public_id + ' entity_urn=' + rec.entity_urn);\n\n"
        "    let urn = rec.entity_urn || '';\n\n"
        "    // URN lookup via dash profiles\n"
        "    if (!urn && rec.public_id) {\n"
        "      console.log('  Looking up URN...');\n"
        "      try {\n"
        "        var url = 'https://www.linkedin.com/voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity=' + encodeURIComponent(rec.public_id);\n"
        "        console.log('  Fetching: ' + url.substring(0, 100));\n"
        "        var dResp = await fetch(url, {\n"
        "          headers: {'csrf-token': csrf, 'x-restli-protocol-version': '2.0.0'},\n"
        "          credentials: 'include'\n"
        "        });\n"
        "        console.log('  Response: ' + dResp.status);\n"
        "        if (dResp.ok) {\n"
        "          var dd = await dResp.json();\n"
        "          console.log('  Included items: ' + (dd.included || []).length);\n"
        "          for (var item of (dd.included || [])) {\n"
        "            var eu = item.entityUrn || '';\n"
        "            if (eu.includes('fsd_profile') || eu.includes('miniProfile')) {\n"
        "              urn = eu;\n"
        "              console.log('  Found URN: ' + urn);\n"
        "              break;\n"
        "            }\n"
        "          }\n"
        "          if (!urn) {\n"
        "            var elems = dd.data && dd.data.elements ? dd.data.elements : (dd.elements || []);\n"
        "            for (var el of elems) {\n"
        "              if (el.entityUrn && el.entityUrn.includes('profile')) { urn = el.entityUrn; break; }\n"
        "            }\n"
        "          }\n"
        "        }\n"
        "      } catch(e) {\n"
        "        console.log('  LOOKUP ERROR: ' + e.message);\n"
        "      }\n"
        "    } else if (!urn) {\n"
        "      console.log('  No public_id to look up');\n"
        "    }\n\n"
        "    if (!urn) {\n"
        "      skipped++;\n"
        "      console.log('  SKIP - no URN found after lookup');\n"
        "      await delay(500);\n"
        "      continue;\n"
        "    }\n\n"
        "    // Send message with the found URN\n"
        "    var memberId = urn.split(':').pop();\n"
        "    var miniUrn = 'urn:li:fs_miniProfile:' + memberId;\n"
        "    console.log('  Sending to: ' + miniUrn);\n\n"
        "    try {\n"
        "      var resp = await fetch('https://www.linkedin.com/voyager/api/messaging/conversations?action=create', {\n"
        "        method: 'POST',\n"
        "        credentials: 'include',\n"
        "        headers: {\n"
        "          'csrf-token': csrf,\n"
        "          'content-type': 'application/json; charset=UTF-8',\n"
        "          'x-restli-protocol-version': '2.0.0'\n"
        "        },\n"
        "        body: JSON.stringify({\n"
        "          keyVersion: 'LEGACY_INBOX',\n"
        "          conversationCreate: {\n"
        "            eventCreate: {\n"
        "              value: { 'com.linkedin.voyager.messaging.create.MessageCreate': {\n"
        "                body: message,\n"
        "                attachments: [],\n"
        "                attributedBody: { text: message, attributes: [] },\n"
        "                mediaAttachments: []\n"
        "              }}\n"
        "            },\n"
        "            recipients: [miniUrn],\n"
        "            subtype: 'MEMBER_TO_MEMBER'\n"
        "          }\n"
        "        })\n"
        "      });\n"
        "      console.log('  Send status: ' + resp.status);\n"
        "      if (resp.ok || resp.status === 201) {\n"
        "        sent++;\n"
        "        console.log('  SENT!');\n"
        "      } else {\n"
        "        var errBody = await resp.text().catch(function() { return ''; });\n"
        "        console.log('  Send error: ' + errBody.substring(0, 150));\n"
        "        failed++;\n"
        "      }\n"
        "    } catch(e) {\n"
        "      console.log('  Send exception: ' + e.message);\n"
        "      failed++;\n"
        "    }\n\n"
        "    await delay(3000 + Math.random() * 3000);\n"
        "  }\n\n"
        "  var summary = 'Done! Sent: ' + sent + ', Failed: ' + failed + ', Skipped: ' + skipped;\n"
        "  console.log('=== ' + summary + ' ===');\n"
        "  alert(summary);\n"
        "})();\n"
    )

    return {"script": script.strip(), "recipients_count": len(recipients)}


@router.get("/message/intercept-script")
async def get_intercept_script():
    """Return a script that intercepts LinkedIn's messaging requests to capture the exact format."""
    script = """
// === LinkedIn Message Interceptor ===
// Captures the EXACT request LinkedIn sends when you message someone
// Step 1: Run this script
// Step 2: Send a message to anyone via LinkedIn's normal UI
// Step 3: The captured format will be logged in the console — copy it

(function() {
  console.log('%c=== Message Interceptor Active ===%c', 'color:#0a66c2;font-size:14px;font-weight:bold', '');
  console.log('Now send a message to someone using LinkedIn\\'s normal UI...');
  console.log('The interceptor will capture the exact request format.');

  // Intercept fetch
  const origFetch = window.fetch;
  window.fetch = async function(...args) {
    const [url, opts] = args;
    const urlStr = typeof url === 'string' ? url : url?.url || '';

    if (urlStr.includes('messaging') && opts?.method?.toUpperCase() === 'POST') {
      console.log('%c=== CAPTURED MESSAGING REQUEST ===%c', 'color:#22c55e;font-size:13px;font-weight:bold', '');
      console.log('URL:', urlStr);
      console.log('Method:', opts.method);

      // Headers
      const hdrs = {};
      if (opts.headers) {
        if (opts.headers instanceof Headers) {
          opts.headers.forEach((v, k) => { hdrs[k] = v; });
        } else if (typeof opts.headers === 'object') {
          Object.assign(hdrs, opts.headers);
        }
      }
      console.log('Headers:', JSON.stringify(hdrs, null, 2));

      // Body
      if (opts.body) {
        try {
          const parsed = JSON.parse(opts.body);
          console.log('Body (parsed):', JSON.stringify(parsed, null, 2));
        } catch(e) {
          console.log('Body (raw):', opts.body);
        }
      }

      console.log('%c=== Copy the above and share with me ===%c', 'color:#f59e0b;font-size:12px;font-weight:bold', '');

      // Also copy to clipboard
      try {
        const captured = { url: urlStr, headers: hdrs, body: opts.body ? JSON.parse(opts.body) : null };
        copy(JSON.stringify(captured, null, 2));
        console.log('(Auto-copied to clipboard!)');
      } catch(e) {}
    }

    return origFetch.apply(this, args);
  };

  // Also intercept XMLHttpRequest
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this._captUrl = url;
    this._captMethod = method;
    return origOpen.apply(this, [method, url, ...rest]);
  };
  XMLHttpRequest.prototype.send = function(body) {
    if (this._captUrl?.includes('messaging') && this._captMethod?.toUpperCase() === 'POST') {
      console.log('%c=== CAPTURED XHR MESSAGING ===%c', 'color:#22c55e;font-size:13px;font-weight:bold', '');
      console.log('URL:', this._captUrl);
      if (body) {
        try { console.log('Body:', JSON.stringify(JSON.parse(body), null, 2)); }
        catch(e) { console.log('Body:', body); }
      }
    }
    return origSend.apply(this, arguments);
  };

  console.log('Interceptor ready. Send a message now...');
})();
"""
    return {
        "script": script.strip(),
        "instructions": [
            "1. Open LinkedIn in Chrome, press F12 → Console → 'allow pasting'",
            "2. Paste this interceptor script → Enter",
            "3. Now send a message to ANY connection using LinkedIn's normal 'Message' button",
            "4. The console will show the EXACT request format captured",
            "5. Copy the captured output and share it with me",
        ]
    }


@router.post("/message/compose-script")
async def generate_compose_script(data: dict):
    """Generate a script that creates a floating UI to message each recipient one by one."""
    recipients = data.get("recipients", [])
    message = data.get("message", "")
    if not recipients or not message:
        raise HTTPException(status_code=400, detail="Recipients and message required")

    message_js = json.dumps(message)
    recipients_js = json.dumps(recipients)

    # Script opens ONE compose tab at a time, panel stays on original tab
    script = """
// === LinkedIn Bulk Compose v6 ===
// Panel stays here. Opens one compose tab at a time.
(function() {
  var R = """ + recipients_js + """;
  var M = """ + message_js + """;
  var idx = 0, sent = 0;

  function copyMsg() {
    try {
      var t = document.createElement('textarea');
      t.value = M; t.style.cssText = 'position:fixed;left:-9999px;top:0';
      document.body.appendChild(t); t.focus(); t.select();
      document.execCommand('copy'); document.body.removeChild(t);
    } catch(e) {}
  }

  // Remove old panel
  var old = document.getElementById('bc-wrap-v6');
  if (old) old.remove();

  var wrap = document.createElement('div');
  wrap.id = 'bc-wrap-v6';
  wrap.style.cssText = 'position:fixed;bottom:80px;right:10px;width:320px;background:#1b1b2f;color:#fff;border-radius:14px;padding:16px;z-index:999999;font-family:system-ui,sans-serif;box-shadow:0 8px 32px rgba(0,0,0,0.6);border:1px solid #333';

  var header = document.createElement('div');
  header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:10px';
  var titleSpan = document.createElement('span');
  titleSpan.style.cssText = 'font-size:13px;font-weight:700';
  titleSpan.textContent = 'Bulk Compose';
  var prog = document.createElement('span');
  prog.style.cssText = 'font-size:11px;color:#94a3b8;margin-left:8px';
  var closeBtn = document.createElement('button');
  closeBtn.textContent = 'X';
  closeBtn.style.cssText = 'background:none;border:none;color:#666;cursor:pointer;font-size:14px;padding:0 4px';
  closeBtn.onclick = function() { wrap.remove(); };
  header.appendChild(titleSpan);
  header.appendChild(prog);
  header.appendChild(closeBtn);
  wrap.appendChild(header);

  var nameEl = document.createElement('div');
  nameEl.style.cssText = 'font-size:15px;font-weight:700;margin-bottom:2px';
  wrap.appendChild(nameEl);

  var occEl = document.createElement('div');
  occEl.style.cssText = 'font-size:10px;color:#94a3b8;margin-bottom:8px';
  wrap.appendChild(occEl);

  var msgPreview = document.createElement('div');
  msgPreview.style.cssText = 'background:#111;border-radius:6px;padding:8px;font-size:10px;color:#aaa;margin-bottom:10px;max-height:40px;overflow:hidden;white-space:pre-wrap';
  msgPreview.textContent = M.length > 100 ? M.substring(0,100) + '...' : M;
  wrap.appendChild(msgPreview);

  var btnRow = document.createElement('div');
  btnRow.style.cssText = 'display:flex;gap:6px;margin-bottom:8px';

  var openBtn = document.createElement('button');
  openBtn.style.cssText = 'flex:1;background:#0a66c2;color:#fff;border:none;padding:10px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600';

  var skipBtn = document.createElement('button');
  skipBtn.textContent = 'Skip';
  skipBtn.style.cssText = 'background:#334155;color:#fff;border:none;padding:10px 14px;border-radius:8px;cursor:pointer;font-size:12px';

  btnRow.appendChild(openBtn);
  btnRow.appendChild(skipBtn);
  wrap.appendChild(btnRow);

  var hint = document.createElement('div');
  hint.style.cssText = 'font-size:9px;color:#64748b;text-align:center;line-height:1.4';
  wrap.appendChild(hint);

  document.body.appendChild(wrap);

  var composeWin = null;

  function show() {
    if (idx >= R.length) {
      nameEl.textContent = 'All done!';
      nameEl.style.color = '#22c55e';
      occEl.textContent = 'Completed: ' + sent + ' sent, ' + (R.length - sent) + ' skipped';
      msgPreview.style.display = 'none';
      btnRow.style.display = 'none';
      hint.textContent = 'You can close this panel now.';
      return;
    }
    var r = R[idx];
    prog.textContent = (idx+1) + '/' + R.length;
    nameEl.textContent = r.name || 'Unknown';
    nameEl.style.color = '#fff';
    occEl.textContent = r.occupation || '';
    openBtn.textContent = 'Compose + Copy Msg';
    hint.innerHTML = 'Opens compose in new tab. Paste message (Ctrl+V), Send, close tab, come back here.';
    copyMsg();
  }

  openBtn.onclick = function() {
    var r = R[idx];
    if (!r || !r.public_id) { idx++; show(); return; }
    copyMsg();
    // Close previous compose tab if still open
    if (composeWin && !composeWin.closed) {
      try { composeWin.close(); } catch(e) {}
    }
    composeWin = window.open('https://www.linkedin.com/messaging/compose/?recipient=' + encodeURIComponent(r.public_id), 'linkedin_compose');
    sent++; idx++;
    show();
  };

  skipBtn.onclick = function() { idx++; show(); };

  show();
  console.log('Bulk Compose v6 ready: ' + R.length + ' recipients. Panel at bottom-right.');
})();
"""

    return {"script": script.strip(), "recipients_count": len(recipients)}

@router.post("/connections/push")
async def push_connections(data: dict):
    """Receive connections — upsert by public_id (no duplicates)."""
    connections = data.get("connections", [])
    if not connections:
        raise HTTPException(status_code=400, detail="No connections data")

    stored = 0
    new_count = 0
    for conn in connections:
        public_id = conn.get("public_id", "")
        if not public_id:
            continue
        occupation = conn.get("occupation", "")
        # Extract company and city from occupation if possible
        company = ""
        city = ""
        if " at " in occupation:
            parts = occupation.split(" at ", 1)
            company = parts[1].strip() if len(parts) > 1 else ""
        elif " @ " in occupation:
            parts = occupation.split(" @ ", 1)
            company = parts[1].strip() if len(parts) > 1 else ""
        # Check if record exists
        existing = await db.li_connections.find_one({"public_id": public_id})
        is_new = existing is None

        update_doc = {
            "first_name": conn.get("first_name", ""),
            "last_name": conn.get("last_name", ""),
            "full_name": conn.get("full_name", ""),
            "occupation": occupation,
            "company": company or (existing.get("company", "") if existing else ""),
            "city": city or (existing.get("city", "") if existing else ""),
            "profile_url": conn.get("profile_url", f"https://www.linkedin.com/in/{public_id}"),
            "avatar_url": conn.get("avatar_url", ""),
            "public_id": public_id,
            "entity_urn": conn.get("entity_urn", "") or (existing.get("entity_urn", "") if existing else ""),
            "synced_at": datetime.now(timezone.utc),
        }
        # Don't overwrite message stats on re-sync
        if is_new:
            update_doc["messages_sent"] = 0
            update_doc["last_contacted"] = None
            update_doc["created_at"] = datetime.now(timezone.utc)

        await db.li_connections.update_one(
            {"public_id": public_id},
            {"$set": update_doc},
            upsert=True
        )
        stored += 1
        if is_new:
            new_count += 1

    total = await db.li_connections.count_documents({})
    return {"success": True, "stored": stored, "new": new_count, "duplicates": stored - new_count, "total": total}


@router.get("/connections")
async def get_connections(
    start: int = 0,
    count: int = 50,
    keyword: str = "",
    sort_by: str = "full_name",
    sort_dir: int = 1,
    filter_contacted: str = "",
    filter_company: str = "",
    filter_city: str = "",
):
    """Fetch connections with rich search, filters, sorting."""
    query = {}
    conditions = []

    if keyword:
        conditions.append({"$or": [
            {"full_name": {"$regex": keyword, "$options": "i"}},
            {"occupation": {"$regex": keyword, "$options": "i"}},
            {"company": {"$regex": keyword, "$options": "i"}},
            {"city": {"$regex": keyword, "$options": "i"}},
            {"public_id": {"$regex": keyword, "$options": "i"}},
        ]})

    if filter_contacted == "yes":
        conditions.append({"messages_sent": {"$gt": 0}})
    elif filter_contacted == "no":
        conditions.append({"$or": [{"messages_sent": 0}, {"messages_sent": {"$exists": False}}]})

    if filter_company:
        conditions.append({"$or": [
            {"company": {"$regex": filter_company, "$options": "i"}},
            {"occupation": {"$regex": filter_company, "$options": "i"}},
        ]})

    if filter_city:
        conditions.append({"city": {"$regex": filter_city, "$options": "i"}})

    if conditions:
        query = {"$and": conditions} if len(conditions) > 1 else conditions[0]

    # Valid sort fields
    valid_sorts = {"full_name": 1, "occupation": 1, "company": 1, "city": 1,
                   "last_contacted": -1, "messages_sent": -1, "synced_at": -1, "created_at": -1}
    sort_field = sort_by if sort_by in valid_sorts else "full_name"

    total = await db.li_connections.count_documents(query)
    cursor = db.li_connections.find(query).sort(sort_field, sort_dir).skip(start).limit(count)
    connections = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        for dt_field in ["synced_at", "last_contacted", "created_at"]:
            if isinstance(doc.get(dt_field), datetime):
                doc[dt_field] = doc[dt_field].isoformat()
        connections.append(doc)

    return {"connections": connections, "total": total, "start": start, "count": count}


@router.get("/connections/{public_id}")
async def get_connection_detail(public_id: str):
    """Get single connection with message history."""
    conn = await db.li_connections.find_one({"public_id": public_id})
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    conn["_id"] = str(conn["_id"])
    for dt_field in ["synced_at", "last_contacted", "created_at"]:
        if isinstance(conn.get(dt_field), datetime):
            conn[dt_field] = conn[dt_field].isoformat()

    # Get message history
    messages = []
    cursor = db.li_message_log.find({"public_id": public_id}).sort("sent_at", -1).limit(50)
    async for msg in cursor:
        msg["_id"] = str(msg["_id"])
        if isinstance(msg.get("sent_at"), datetime):
            msg["sent_at"] = msg["sent_at"].isoformat()
        messages.append(msg)

    conn["message_history"] = messages
    return conn


@router.post("/messages/log")
async def log_message(data: dict):
    """Log a sent message for tracking."""
    public_id = data.get("public_id", "")
    message = data.get("message", "")
    recipient_name = data.get("recipient_name", "")
    if not public_id or not message:
        raise HTTPException(status_code=400, detail="public_id and message required")

    now = datetime.now(timezone.utc)
    await db.li_message_log.insert_one({
        "public_id": public_id,
        "recipient_name": recipient_name,
        "message": message,
        "sent_at": now,
    })
    # Update contact stats
    await db.li_connections.update_one(
        {"public_id": public_id},
        {"$set": {"last_contacted": now}, "$inc": {"messages_sent": 1}}
    )
    return {"success": True}


@router.get("/messages/log")
async def get_message_log(
    start: int = 0,
    count: int = 50,
    public_id: str = "",
):
    """Get message log / report."""
    query = {}
    if public_id:
        query["public_id"] = public_id
    total = await db.li_message_log.count_documents(query)
    cursor = db.li_message_log.find(query).sort("sent_at", -1).skip(start).limit(count)
    messages = []
    async for msg in cursor:
        msg["_id"] = str(msg["_id"])
        if isinstance(msg.get("sent_at"), datetime):
            msg["sent_at"] = msg["sent_at"].isoformat()
        messages.append(msg)
    return {"messages": messages, "total": total}


@router.get("/connections/stats/overview")
async def get_connections_stats():
    """Get overview stats for the CRM."""
    total = await db.li_connections.count_documents({})
    contacted = await db.li_connections.count_documents({"messages_sent": {"$gt": 0}})
    total_messages = await db.li_message_log.count_documents({})
    # Top companies
    pipeline = [
        {"$match": {"company": {"$ne": "", "$exists": True}}},
        {"$group": {"_id": "$company", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    top_companies = []
    async for doc in db.li_connections.aggregate(pipeline):
        top_companies.append({"company": doc["_id"], "count": doc["count"]})

    return {
        "total_connections": total,
        "contacted": contacted,
        "not_contacted": total - contacted,
        "total_messages": total_messages,
        "top_companies": top_companies,
    }


@router.get("/message/queue")
async def get_message_queue():
    """Get pending message queue for the Chrome extension."""
    queue = await db.li_message_queue.find_one({"status": "pending"}, sort=[("created_at", -1)])
    if not queue:
        return {"recipients": [], "message": ""}
    queue["_id"] = str(queue["_id"])
    return {
        "recipients": queue.get("recipients", []),
        "message": queue.get("message", ""),
        "queue_id": queue["_id"]
    }


@router.post("/message/queue")
async def create_message_queue(data: dict):
    """Create a message queue for the Chrome extension to pick up."""
    recipients = data.get("recipients", [])
    message = data.get("message", "")
    if not recipients or not message:
        raise HTTPException(status_code=400, detail="Recipients and message required")
    doc = {
        "recipients": recipients,
        "message": message,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.li_message_queue.insert_one(doc)
    return {"success": True, "queue_id": str(result.inserted_id), "count": len(recipients)}



@router.get("/browser-script")
async def get_browser_script():
    """Return script to sync ALL first-degree LinkedIn connections."""

    script = """
// === LinkedIn Connection Sync v11 ===
// Tries multiple API approaches to get ALL 1st degree connections

(async () => {
  console.log('=== LinkedIn Sync v11 ===');
  var delay = function(ms) { return new Promise(function(r) { setTimeout(r, ms); }); };
  var csrf = (document.cookie.match(/JSESSIONID="?([^;"]+)/) || [])[1] || '';
  if (!csrf) { alert('Not logged into LinkedIn'); return; }
  var H = {'csrf-token': csrf, 'x-restli-protocol-version': '2.0.0'};
  var results = [];
  var seenIds = {};

  function addResult(pid, fn, ln, occ, urn) {
    if (!pid || seenIds[pid]) return false;
    seenIds[pid] = true;
    results.push({
      full_name: ((fn||'') + ' ' + (ln||'')).trim(),
      first_name: fn || '', last_name: ln || '',
      occupation: occ || '',
      profile_url: 'https://www.linkedin.com/in/' + pid,
      public_id: pid, entity_urn: urn || '', avatar_url: ''
    });
    return true;
  }

  function extractFromIncluded(included) {
    var count = 0;
    for (var i = 0; i < included.length; i++) {
      var item = included[i];
      if (!item.firstName) continue;
      var pid = item.publicIdentifier || '';
      var urn = item.entityUrn || '';
      if (!pid && urn) {
        // Try to extract from objectUrn or other fields
        pid = item.vanityName || '';
      }
      if (pid && addResult(pid, item.firstName, item.lastName, item.occupation, urn)) count++;
    }
    return count;
  }

  // ========== METHOD A: Connections API with decoration range -5 to -25 ==========
  console.log('Method A: Connections API...');
  var apiWorked = false;

  for (var decNum = 5; decNum <= 25; decNum++) {
    if (apiWorked) break;
    try {
      var url = 'https://www.linkedin.com/voyager/api/relationships/dash/connections'
        + '?decorationId=com.linkedin.voyager.dash.deco.web.mynetwork.ConnectionListWithProfile-' + decNum
        + '&count=40&q=search&sortType=RECENTLY_ADDED&start=0';
      var resp = await fetch(url, {headers: H, credentials: 'include'});
      if (!resp.ok) continue;
      var data = await resp.json();
      var included = data.included || [];
      // Find total from paging - check all possible locations
      var total = 0;
      if (data.data && data.data.paging) total = data.data.paging.total || data.data.paging.count || 0;
      if (!total && data.paging) total = data.paging.total || data.paging.count || 0;
      if (!total && data.data && data.data['*elements']) total = data.data['*elements'].length || 0;
      // If no total found but included has items, estimate
      if (!total && included.length > 0) total = 99999;

      var added = extractFromIncluded(included);
      if (added > 0) {
        apiWorked = true;
        console.log('  Decoration -' + decNum + ' works! Added ' + added + ', total~' + total);
        // Paginate
        for (var s = 40; s < total; s += 40) {
          await delay(400 + Math.random() * 200);
          try {
            var nu = 'https://www.linkedin.com/voyager/api/relationships/dash/connections'
              + '?decorationId=com.linkedin.voyager.dash.deco.web.mynetwork.ConnectionListWithProfile-' + decNum
              + '&count=40&q=search&sortType=RECENTLY_ADDED&start=' + s;
            var nr = await fetch(nu, {headers: H, credentials: 'include'});
            if (!nr.ok) { console.log('  Stopped at ' + s + ': HTTP ' + nr.status); break; }
            var nd = await nr.json();
            var before = results.length;
            extractFromIncluded(nd.included || []);
            var newAdded = results.length - before;
            if (s % 200 === 0) console.log('  Progress: ' + results.length + ' connections fetched...');
            if (newAdded === 0) break;
          } catch(e) { break; }
        }
        console.log('  Method A done: ' + results.length + ' connections');
      }
    } catch(e) {}
  }

  // ========== METHOD B: Search API with 1st degree filter ==========
  if (!apiWorked) {
    console.log('Method B: Search API (1st degree)...');
    try {
      for (var s = 0; s < 50000; s += 49) {
        var searchUrl = 'https://www.linkedin.com/voyager/api/search/dash/clusters'
          + '?decorationId=com.linkedin.voyager.dash.deco.search.SearchClusterCollection-186'
          + '&origin=FACETED_SEARCH&q=all'
          + '&query=(flagshipSearchIntent:SEARCH_SRP,queryParameters:List((key:network,value:List(F)),(key:resultType,value:List(PEOPLE))))'
          + '&count=49&start=' + s;
        var sr = await fetch(searchUrl, {headers: H, credentials: 'include'});
        if (!sr.ok) {
          // Try alternate decoration
          if (s === 0) {
            for (var sd = 160; sd <= 200; sd += 5) {
              searchUrl = 'https://www.linkedin.com/voyager/api/search/dash/clusters'
                + '?decorationId=com.linkedin.voyager.dash.deco.search.SearchClusterCollection-' + sd
                + '&origin=FACETED_SEARCH&q=all'
                + '&query=(flagshipSearchIntent:SEARCH_SRP,queryParameters:List((key:network,value:List(F)),(key:resultType,value:List(PEOPLE))))'
                + '&count=49&start=0';
              sr = await fetch(searchUrl, {headers: H, credentials: 'include'});
              if (sr.ok) { console.log('  Search decoration -' + sd + ' works'); break; }
            }
          }
          if (!sr.ok) { console.log('  Search API failed: ' + sr.status); break; }
        }
        var sd = await sr.json();
        var before = results.length;
        extractFromIncluded(sd.included || []);
        var added = results.length - before;
        if (s === 0) console.log('  First page: +' + added);
        if (s % 490 === 0 && s > 0) console.log('  Search progress: ' + results.length + ' found...');
        if (added === 0) break;
        apiWorked = results.length > 0;
        await delay(400 + Math.random() * 300);
      }
      if (apiWorked) console.log('  Method B done: ' + results.length + ' connections');
    } catch(e) { console.log('  Search error: ' + e.message); }
  }

  // ========== METHOD C: Plain connections API without decoration ==========
  if (!apiWorked) {
    console.log('Method C: Plain connections API...');
    try {
      var pr = await fetch('https://www.linkedin.com/voyager/api/relationships/dash/connections?q=search&sortType=RECENTLY_ADDED&count=40&start=0', {headers: H, credentials: 'include'});
      if (pr.ok) {
        var pd = await pr.json();
        // Log response structure for debugging
        console.log('  Response keys: ' + Object.keys(pd).join(', '));
        if (pd.data) console.log('  data keys: ' + Object.keys(pd.data).join(', '));
        console.log('  included length: ' + (pd.included || []).length);
        var added = extractFromIncluded(pd.included || []);
        if (added > 0) {
          apiWorked = true;
          console.log('  Plain API works: +' + added);
          for (var s = 40; s < 50000; s += 40) {
            await delay(500);
            try {
              var nr = await fetch('https://www.linkedin.com/voyager/api/relationships/dash/connections?q=search&sortType=RECENTLY_ADDED&count=40&start=' + s, {headers: H, credentials: 'include'});
              if (!nr.ok) break;
              var nd = await nr.json();
              var before = results.length;
              extractFromIncluded(nd.included || []);
              if (results.length === before) break;
              if (s % 200 === 0) console.log('  Progress: ' + results.length);
            } catch(e) { break; }
          }
        } else {
          console.log('  No connections in included. Checking elements...');
          var elems = pd.data && pd.data.elements ? pd.data.elements : (pd.elements || []);
          console.log('  Elements: ' + elems.length);
          // elements might contain URN references
          for (var i = 0; i < Math.min(elems.length, 3); i++) {
            console.log('  Sample element: ' + JSON.stringify(elems[i]).substring(0, 200));
          }
        }
      }
    } catch(e) { console.log('  Error: ' + e.message); }
  }

  // ========== METHOD D: DOM scraping with auto-scroll ==========
  if (results.length < 100) {
    console.log('Method D: DOM scraping with auto-scroll...');
    var scrollCount = 0;
    var maxScrolls = 50;
    var lastCount = 0;

    while (scrollCount < maxScrolls) {
      // Scrape current visible profiles
      document.querySelectorAll('a[href*="/in/"]').forEach(function(link) {
        try {
          var href = link.href.split('?')[0].replace(/\\/$/, '');
          var m = href.match(/\\/in\\/([a-zA-Z0-9_-]+)/);
          if (!m) return;
          var pid = m[1];
          if (seenIds[pid] || pid.length > 100 || pid.length < 2) return;
          if (link.closest('nav') || link.closest('header') || link.closest('footer')) return;
          var container = link.parentElement;
          for (var i = 0; i < 8 && container; i++) {
            var txt = container.innerText || '';
            if (txt.length > 30 && txt.length < 2000) break;
            container = container.parentElement;
          }
          var ct = (container && container.innerText || '').trim();
          if (ct.length < 5) return;
          var lines = ct.split('\\n').map(function(l){return l.trim()}).filter(function(l) {
            return l.length > 1 && l.length < 80 && ['Message','Connect','Follow','Pending','More','...','Promoted'].indexOf(l) === -1;
          });
          var fn = '', occ = '';
          for (var li = 0; li < lines.length; li++) {
            if (!fn && lines[li].length <= 50 && lines[li].indexOf('|') === -1 && lines[li].indexOf('mutual') === -1) { fn = lines[li]; continue; }
            if (fn && !occ && lines[li].indexOf('mutual') === -1 && lines[li].length > 3) { occ = lines[li]; break; }
          }
          if (!fn || fn.length < 2) return;
          var parts = fn.split(' ');
          addResult(pid, parts[0], parts.slice(1).join(' '), occ, '');
        } catch(e) {}
      });

      if (results.length === lastCount) {
        // No new results after scroll — try clicking "Show more"
        var showMore = document.querySelector('button.scaffold-finite-scroll__load-button, button[aria-label*="Show more"]');
        if (showMore) { showMore.click(); await delay(2000); }
        else break;
      }
      lastCount = results.length;
      scrollCount++;
      window.scrollTo(0, document.body.scrollHeight);
      await delay(1500);
      if (scrollCount % 10 === 0) console.log('  Scrolled ' + scrollCount + 'x, found ' + results.length + ' connections');
    }
    console.log('DOM scrape done: ' + results.length + ' connections');
  }

  // ========== DONE ==========
  if (results.length === 0) {
    alert('No connections found. Make sure you are logged into LinkedIn.');
    return;
  }

  var withUrn = results.filter(function(r){return r.entity_urn}).length;
  try { copy(JSON.stringify(results)); } catch(e) {
    var ta = document.createElement('textarea');
    ta.value = JSON.stringify(results);
    ta.style.cssText = 'position:fixed;left:-9999px';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
  }

  var preview = results.slice(0,3).map(function(c){return c.full_name}).join(', ');
  var msg = 'Copied ' + results.length + ' connections (' + withUrn + ' with URN)!\\nPreview: ' + preview + '...\\nPaste in Lead Finder > Messaging > Import';
  console.log(msg);
  alert(msg);
})();
"""
    return {"script": script.strip(), "instructions": [
        "1. Go to LinkedIn Connections page (linkedin.com/mynetwork/invite-connect/connections/)",
        "2. Press F12 → Console → type 'allow pasting' → Enter",
        "3. Paste the script → Enter",
        "4. Wait — it tries multiple APIs, then auto-scrolls to load more",
        "5. When done, paste results in Lead Finder → Messaging → Import"
    ]}
