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
        "// === LinkedIn Bulk Messenger v3 ===\n"
        "// Uses profile lookup (not typeahead) to resolve URNs, then sends messages\n"
        "// Run on any linkedin.com page\n\n"
        "(async () => {\n"
        "  const recipients = " + recipients_js + ";\n"
        "  const message = " + message_js + ";\n"
        "  let sent = 0, failed = 0, skipped = 0;\n"
        "  const delay = ms => new Promise(r => setTimeout(r, ms));\n"
        "  const csrf = (document.cookie.match(/JSESSIONID=\"?([^;\"]+)/) || [])[1] || '';\n"
        "  if (!csrf) { alert('Not logged in to LinkedIn'); return; }\n"
        "  const H = {'csrf-token': csrf, 'x-restli-protocol-version': '2.0.0'};\n"
        "  const HP = {...H, 'content-type': 'application/json'};\n\n"
        "  console.log('=== Bulk Messenger: ' + recipients.length + ' recipients ===');\n\n"
        "  for (let i = 0; i < recipients.length; i++) {\n"
        "    const rec = recipients[i];\n"
        "    console.log('(' + (i+1) + '/' + recipients.length + ') ' + rec.name);\n\n"
        "    let urn = rec.entity_urn || '';\n\n"
        "    // Step 1: If no URN, look up via direct profile API (stable endpoint)\n"
        "    if (!urn && rec.public_id) {\n"
        "      try {\n"
        "        const pResp = await fetch(\n"
        "          'https://www.linkedin.com/voyager/api/identity/profiles/' + encodeURIComponent(rec.public_id) + '/profileView',\n"
        "          {headers: H}\n"
        "        );\n"
        "        if (pResp.ok) {\n"
        "          const pd = await pResp.json();\n"
        "          for (const item of (pd.included || [])) {\n"
        "            if (item.entityUrn && item.entityUrn.includes('fsd_profile')) {\n"
        "              urn = item.entityUrn; break;\n"
        "            }\n"
        "          }\n"
        "          if (!urn) {\n"
        "            const mp = pd.profile || {};\n"
        "            if (mp.entityUrn) urn = mp.entityUrn;\n"
        "            else if (mp.miniProfile?.entityUrn) urn = mp.miniProfile.entityUrn;\n"
        "          }\n"
        "          if (urn) console.log('  URN from profile: ' + urn);\n"
        "        } else {\n"
        "          console.log('  Profile lookup: HTTP ' + pResp.status);\n"
        "        }\n"
        "      } catch(e) { console.log('  Profile lookup error: ' + e.message); }\n"
        "    }\n\n"
        "    // Step 2: Fallback — try dash/profiles endpoint\n"
        "    if (!urn && rec.public_id) {\n"
        "      try {\n"
        "        const dResp = await fetch(\n"
        "          'https://www.linkedin.com/voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity=' + encodeURIComponent(rec.public_id),\n"
        "          {headers: H}\n"
        "        );\n"
        "        if (dResp.ok) {\n"
        "          const dd = await dResp.json();\n"
        "          const elems = dd.data?.elements || dd.elements || [];\n"
        "          for (const el of elems) {\n"
        "            if (el.entityUrn?.includes('fsd_profile')) { urn = el.entityUrn; break; }\n"
        "          }\n"
        "          if (!urn) {\n"
        "            for (const item of (dd.included || [])) {\n"
        "              if (item.entityUrn?.includes('fsd_profile')) { urn = item.entityUrn; break; }\n"
        "            }\n"
        "          }\n"
        "          if (urn) console.log('  URN from dash: ' + urn);\n"
        "        }\n"
        "      } catch(e) {}\n"
        "    }\n\n"
        "    if (!urn) {\n"
        "      skipped++;\n"
        "      console.log('  SKIP — no URN found for ' + (rec.public_id || rec.name));\n"
        "      await delay(500);\n"
        "      continue;\n"
        "    }\n\n"
        "    // Step 3: Send message (try new endpoint first, then old)\n"
        "    try {\n"
        "      let ok = false;\n"
        "      // Method A: New Voyager messaging\n"
        "      let resp = await fetch('https://www.linkedin.com/voyager/api/voyagerMessagingDashMessengerMessages?action=createMessage', {\n"
        "        method: 'POST', headers: HP,\n"
        "        body: JSON.stringify({\n"
        "          message: {body: {text: message, attributes: []}, renderContentUnions: []},\n"
        "          recipients: [urn],\n"
        "          dedupeByClientGeneratedToken: false\n"
        "        })\n"
        "      });\n"
        "      if (resp.ok || resp.status === 201) { ok = true; }\n"
        "      else { console.log('  Method A: ' + resp.status); }\n\n"
        "      // Method B: Classic messaging endpoint\n"
        "      if (!ok) {\n"
        "        resp = await fetch('https://www.linkedin.com/voyager/api/messaging/conversations?action=create', {\n"
        "          method: 'POST', headers: HP,\n"
        "          body: JSON.stringify({\n"
        "            conversationCreate: {\n"
        "              eventCreate: {value: {'com.linkedin.voyager.messaging.create.MessageCreate': {\n"
        "                attributedBody: {text: message, attributes: []}, attachments: []\n"
        "              }}},\n"
        "              recipients: [urn], subtype: 'MEMBER_TO_MEMBER'\n"
        "            }\n"
        "          })\n"
        "        });\n"
        "        if (resp.ok || resp.status === 201) { ok = true; }\n"
        "        else { console.log('  Method B: ' + resp.status); }\n"
        "      }\n\n"
        "      if (ok) { sent++; console.log('  SENT'); }\n"
        "      else {\n"
        "        failed++;\n"
        "        try { const et = await resp.text(); console.log('  FAIL: ' + et.substring(0,150)); } catch(e) {}\n"
        "      }\n"
        "    } catch(e) { failed++; console.error('  Error: ' + e.message); }\n\n"
        "    // Rate limiting: 3-6s random delay between messages\n"
        "    await delay(3000 + Math.random() * 3000);\n"
        "  }\n\n"
        "  const summary = 'Done! Sent: ' + sent + ', Failed: ' + failed + ', Skipped: ' + skipped;\n"
        "  console.log('=== ' + summary + ' ===');\n"
        "  alert(summary);\n"
        "})();\n"
    )

    return {"script": script.strip(), "recipients_count": len(recipients)}


# ==================== BROWSER PUSH ENDPOINTS ====================

@router.post("/connections/push")
async def push_connections(data: dict):
    """Receive connections data pushed from browser console script."""
    connections = data.get("connections", [])
    if not connections:
        raise HTTPException(status_code=400, detail="No connections data")

    stored = 0
    for conn in connections:
        public_id = conn.get("public_id", "")
        if not public_id:
            continue
        # Upsert by public_id
        await db.li_connections.update_one(
            {"public_id": public_id},
            {"$set": {
                "first_name": conn.get("first_name", ""),
                "last_name": conn.get("last_name", ""),
                "full_name": conn.get("full_name", ""),
                "occupation": conn.get("occupation", ""),
                "profile_url": conn.get("profile_url", f"https://www.linkedin.com/in/{public_id}"),
                "avatar_url": conn.get("avatar_url", ""),
                "public_id": public_id,
                "entity_urn": conn.get("entity_urn", ""),
                "urn": conn.get("urn", conn.get("entity_urn", "")),
                "synced_at": datetime.now(timezone.utc),
            }},
            upsert=True
        )
        stored += 1

    return {"success": True, "stored": stored, "total": await db.li_connections.count_documents({})}


@router.get("/connections")
async def get_connections(
    start: int = 0,
    count: int = 40,
    keyword: str = ""
):
    """Fetch stored LinkedIn connections."""
    query = {}
    if keyword:
        query["$or"] = [
            {"full_name": {"$regex": keyword, "$options": "i"}},
            {"first_name": {"$regex": keyword, "$options": "i"}},
            {"last_name": {"$regex": keyword, "$options": "i"}},
            {"occupation": {"$regex": keyword, "$options": "i"}},
        ]

    total = await db.li_connections.count_documents(query)
    cursor = db.li_connections.find(query).sort("full_name", 1).skip(start).limit(count)
    connections = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("synced_at"), datetime):
            doc["synced_at"] = doc["synced_at"].isoformat()
        connections.append(doc)

    return {
        "connections": connections,
        "total": total,
        "start": start,
        "count": count
    }


@router.get("/browser-script")
async def get_browser_script():
    """Return a simple, bulletproof browser script to sync LinkedIn connections."""

    script = """
// === LinkedIn Connection Sync v9 ===
// Works on ANY LinkedIn page. Scrapes visible profiles + fetches URNs.
// Run in Chrome DevTools Console (F12 → Console → type 'allow pasting')

(async () => {
  console.log('%c=== LinkedIn Sync v9 Starting ===', 'color: #0a66c2; font-size: 14px; font-weight: bold');

  const delay = ms => new Promise(r => setTimeout(r, ms));
  const csrf = (document.cookie.match(/JSESSIONID="?([^;"]+)/) || [])[1] || '';
  if (!csrf) { alert('ERROR: Not logged into LinkedIn. Please log in first.'); return; }
  console.log('CSRF token found. Starting sync...');

  const H = {'csrf-token': csrf, 'x-restli-protocol-version': '2.0.0'};
  const results = [];
  const seenIds = new Set();

  // ========== METHOD 1: Scrape profiles visible on this page ==========
  console.log('Step 1: Scraping profiles from current page...');
  document.querySelectorAll('a[href*="/in/"]').forEach(link => {
    try {
      const href = link.href.split('?')[0].replace(/\\/$/, '');
      const match = href.match(/\\/in\\/([a-zA-Z0-9_-]+)/);
      if (!match) return;
      const publicId = match[1];
      if (seenIds.has(publicId) || publicId.length > 100 || publicId.length < 2) return;
      if (link.closest('nav') || link.closest('header') || link.closest('footer')) return;

      // Walk up to find the card container
      let container = link.parentElement;
      for (let i = 0; i < 8 && container; i++) {
        const text = container.innerText || '';
        if (text.length > 30 && text.length < 2000) break;
        container = container.parentElement;
      }

      const cardText = (container?.innerText || '').trim();
      if (cardText.length < 5) return;

      // Extract name: first non-empty line that's not a badge/button
      const lines = cardText.split('\\n').map(l => l.trim()).filter(l =>
        l.length > 1 && l.length < 80 &&
        !['Message', 'Connect', 'Follow', 'Pending', 'More', '...', 'Promoted'].includes(l) &&
        !l.startsWith('Sent') && !l.startsWith('Connected') && !l.match(/^\\d/)
      );

      let fullName = '';
      let occupation = '';
      for (const line of lines) {
        if (!fullName && line.length <= 50 && !line.includes('|') && !line.includes('mutual')) {
          fullName = line.replace(/[\\u2022\\u00B7]/g, '').trim();
          continue;
        }
        if (fullName && !occupation && !line.includes('mutual') && line.length > 3) {
          occupation = line;
          break;
        }
      }
      if (!fullName || fullName.length < 2) return;

      seenIds.add(publicId);
      const parts = fullName.split(' ');
      results.push({
        full_name: fullName,
        first_name: parts[0] || '',
        last_name: parts.slice(1).join(' ') || '',
        occupation: occupation || '',
        profile_url: 'https://www.linkedin.com/in/' + publicId,
        public_id: publicId,
        entity_urn: '',
        avatar_url: ''
      });
    } catch(e) {}
  });
  console.log('Found ' + results.length + ' profiles on page');

  // ========== METHOD 2: Also try Connections API for bulk fetch ==========
  if (results.length < 10) {
    console.log('Step 2: Fetching more via Connections API...');
    const decorations = ['-16', '-15', '-14', '-13'];
    let apiWorked = false;

    for (const dec of decorations) {
      if (apiWorked) break;
      try {
        const url = 'https://www.linkedin.com/voyager/api/relationships/dash/connections'
          + '?decorationId=com.linkedin.voyager.dash.deco.web.mynetwork.ConnectionListWithProfile' + dec
          + '&count=40&q=search&sortType=RECENTLY_ADDED&start=0';
        const resp = await fetch(url, {headers: H});
        if (resp.ok) {
          const data = await resp.json();
          const total = data.data?.paging?.total || data.paging?.total || 0;
          console.log('Connections API (decoration' + dec + '): Total=' + total);

          // Process up to 500 connections
          let processed = 0;
          const processPage = (d) => {
            for (const item of (d.included || [])) {
              if (!item.firstName || !item.entityUrn) continue;
              const urn = item.entityUrn || '';
              if (!urn.includes('fsd_profile') && !urn.includes('miniProfile')) continue;
              const pid = item.publicIdentifier || '';
              if (!pid || seenIds.has(pid)) continue;
              seenIds.add(pid);
              results.push({
                full_name: ((item.firstName||'') + ' ' + (item.lastName||'')).trim(),
                first_name: item.firstName || '',
                last_name: item.lastName || '',
                occupation: item.occupation || '',
                profile_url: 'https://www.linkedin.com/in/' + pid,
                public_id: pid,
                entity_urn: urn,
                avatar_url: ''
              });
              processed++;
            }
          };

          processPage(data);
          apiWorked = true;
          console.log('  Page 1: +' + processed + ' connections');

          // Fetch more pages
          for (let s = 40; s < Math.min(total, 500); s += 40) {
            await delay(600);
            try {
              const nextUrl = 'https://www.linkedin.com/voyager/api/relationships/dash/connections'
                + '?decorationId=com.linkedin.voyager.dash.deco.web.mynetwork.ConnectionListWithProfile' + dec
                + '&count=40&q=search&sortType=RECENTLY_ADDED&start=' + s;
              const nr = await fetch(nextUrl, {headers: H});
              if (nr.ok) {
                const before = results.length;
                processPage(await nr.json());
                const added = results.length - before;
                console.log('  Page ' + (Math.floor(s/40)+1) + ': +' + added + ' (total: ' + results.length + ')');
                if (added === 0) break;
              } else break;
            } catch(e) { break; }
          }
        } else {
          console.log('Connections API decoration' + dec + ': HTTP ' + resp.status);
        }
      } catch(e) {
        console.log('Connections API error: ' + e.message);
      }
    }
  }

  // ========== METHOD 3: Get URNs for profiles that don't have them ==========
  const needUrn = results.filter(r => !r.entity_urn);
  if (needUrn.length > 0) {
    console.log('Step 3: Looking up URNs for ' + needUrn.length + ' profiles...');
    let urnOk = 0, urnFail = 0;
    for (let i = 0; i < needUrn.length; i++) {
      const c = needUrn[i];
      try {
        const r = await fetch('https://www.linkedin.com/voyager/api/identity/profiles/' + encodeURIComponent(c.public_id) + '/profileView', {headers: H});
        if (r.ok) {
          const d = await r.json();
          for (const item of (d.included || [])) {
            if (item.entityUrn && item.entityUrn.includes('fsd_profile')) {
              c.entity_urn = item.entityUrn;
              urnOk++;
              break;
            }
          }
          if (!c.entity_urn) urnFail++;
        } else {
          console.log('  Profile ' + c.public_id + ': HTTP ' + r.status);
          urnFail++;
        }
      } catch(e) { urnFail++; }
      if (i % 5 === 4) {
        console.log('  URN progress: ' + (i+1) + '/' + needUrn.length + ' (' + urnOk + ' found)');
        await delay(500);
      }
    }
    console.log('URN lookup complete: ' + urnOk + ' found, ' + urnFail + ' failed');
  }

  // ========== DONE: Copy results ==========
  const withUrn = results.filter(r => r.entity_urn).length;
  if (results.length === 0) {
    alert('No profiles found on this page.\\n\\nTry:\\n1. Go to LinkedIn connections page\\n2. Scroll down to load more\\n3. Run script again');
    return;
  }

  try {
    copy(JSON.stringify(results));
  } catch(e) {
    // Fallback for copy()
    const ta = document.createElement('textarea');
    ta.value = JSON.stringify(results);
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }

  const preview = results.slice(0,3).map(c => c.full_name).join(', ');
  const msg = 'SUCCESS! Copied ' + results.length + ' connections (' + withUrn + ' with URN)\\n\\nPreview: ' + preview + '...\\n\\nNow go to Lead Finder → Messaging tab → Paste & Import';
  console.log('%c' + msg, 'color: #22c55e; font-size: 13px');
  alert(msg);
})();
"""
    return {"script": script.strip(), "instructions": [
        "1. Open LinkedIn (any page — connections page, search results, or even your feed)",
        "2. SCROLL DOWN to load the profiles you want to sync",
        "3. Press F12 → Console tab → type 'allow pasting' and press Enter",
        "4. Paste the script and press Enter",
        "5. Watch the console for progress messages",
        "6. When the alert appears — data is copied to your clipboard",
        "7. Go to Lead Finder → Messaging → paste in the import box → Import"
    ]}
