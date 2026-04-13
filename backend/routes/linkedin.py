import os
import time
import httpx
import secrets
import logging
import uuid
import base64
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/linkedin", tags=["linkedin"])

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# LinkedIn OAuth config
LINKEDIN_CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET")
LINKEDIN_REDIRECT_URI = os.environ.get("LINKEDIN_REDIRECT_URI")
LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
LINKEDIN_POSTS_URL = "https://api.linkedin.com/rest/posts"
LINKEDIN_API_VERSION = "202502"

# In-memory state storage for OAuth CSRF (short-lived, cleanup on server restart is acceptable)
oauth_states = {}

# Company content contexts
COMPANY_CONTEXTS = {
    "fundle": {
        "name": "Fundle.ai",
        "tagline": "First-Party Retail Data Intelligence",
        "description": "Fundle is a Retail Intelligence Platform powering malls, brands, and consumers through unified data, AI insights, and monetisation rails.",
        "products": [
            "ADSR/BI Suite - Automated Daily Sales Reporting with real-time dashboards",
            "Loyalty (Mall + Brand) - Unified loyalty infrastructure with AI/GPT-powered personalization",
            "FundleXperiences (D2C) - Games, rewards, bill-based consumer engagement",
            "Fundle Reach (Media Engine) - Mall media inventory, physical + digital monetisation",
            "Fundle One (Mall Card) - Payment-linked identity and spend tracking",
            "Fundle E-Commerce - Mall-wide digital commerce with loyalty-integrated checkout"
        ],
        "value_props": [
            "First-party data ownership (no walled garden dependency)",
            "Cross-ecosystem intelligence across malls, brands, consumers",
            "AI-driven GPT-powered personalization",
            "Scalable pan-India retail infrastructure",
            "Multiple monetisation: SaaS, Media, Performance Marketing, Financial Products, D2C"
        ],
        "target_audience": "Mall operators, retail brands, shopping centre management, retail CXOs",
        "website": "https://www.fundle.ai",
        "hashtags": "#RetailIntelligence #RetailTech #MallTech #FirstPartyData #FundleAI #RetailData #ShoppingMalls #RetailAnalytics #D2C #LoyaltyPrograms"
    },
    "hearclear": {
        "name": "HearClear India",
        "tagline": "Advanced Hearing Healthcare",
        "description": "HearClear India is a hearing healthcare company providing advanced audiology solutions, hearing aids, and hearing care services across India.",
        "products": [
            "Hearing aids and assistive devices",
            "Audiology diagnostics and testing",
            "Hearing rehabilitation programs",
            "Tele-audiology services"
        ],
        "value_props": [
            "Expert audiology care",
            "Latest hearing technology",
            "Pan-India presence",
            "Personalized hearing solutions"
        ],
        "target_audience": "People with hearing difficulties, ENT specialists, healthcare providers, senior care",
        "website": "https://www.hearclearindia.com",
        "hashtags": "#HearingHealth #Audiology #HearClear #HearingAids #HealthTech #HearingCare #India"
    },
    "tagnpay": {
        "name": "Tagnpay.ai",
        "tagline": "B2B Channel Loyalty for Manufacturers",
        "description": "Tagnpay.ai is a B2B channel loyalty platform for manufacturers to incentivize and engage their distribution channel partners - distributors, dealers, retailers, and influencers.",
        "products": [
            "Channel loyalty programs for manufacturers",
            "QR/NFC-based product authentication and reward scanning",
            "Distributor and dealer engagement platform",
            "Channel partner analytics and insights"
        ],
        "value_props": [
            "Direct manufacturer-to-channel engagement",
            "Anti-counterfeiting with product authentication",
            "Real-time channel analytics",
            "Gamified loyalty for trade partners"
        ],
        "target_audience": "Manufacturers, FMCG brands, building materials companies, channel sales teams",
        "website": "https://www.tagnpay.ai",
        "hashtags": "#ChannelLoyalty #B2B #ManufacturerLoyalty #TagnPay #DistributorEngagement #TradeMarketing"
    }
}


# ============== Pydantic Models ==============
class LinkedInPostRequest(BaseModel):
    account_id: str
    company: str
    content: str
    post_type: str = "text"
    link_url: Optional[str] = None
    link_title: Optional[str] = None

class ContentGenerateRequest(BaseModel):
    company: str
    topic: Optional[str] = None
    tone: str = "professional"
    post_count: int = 1

class ScheduleRequest(BaseModel):
    account_id: str
    company: str
    interval_hours: int = 4
    enabled: bool = True


# ============== OAuth Endpoints ==============
@router.get("/auth")
async def linkedin_auth():
    """Generate LinkedIn OAuth URL and redirect user."""
    if not LINKEDIN_CLIENT_ID:
        raise HTTPException(status_code=500, detail="LinkedIn Client ID not configured")

    state = secrets.token_urlsafe(32)
    # Store in MongoDB so it survives server restarts
    await db.oauth_states.insert_one({
        "state": state,
        "created_at": time.time(),
        "used": False
    })

    scopes = "openid profile w_member_social"
    from urllib.parse import quote
    params = (
        f"response_type=code"
        f"&client_id={LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={quote(LINKEDIN_REDIRECT_URI, safe='')}"
        f"&state={state}"
        f"&scope={quote(scopes, safe='')}"
    )
    auth_url = f"{LINKEDIN_AUTH_URL}?{params}"
    return {"auth_url": auth_url, "state": state}


@router.get("/callback")
async def linkedin_callback(code: str = Query(None), state: str = Query(None), error: str = Query(None), error_description: str = Query(None)):
    """Handle LinkedIn OAuth callback."""
    if error:
        logger.error(f"LinkedIn OAuth error: {error} - {error_description}")
        return HTMLResponse(content=f"""
        <html><body>
        <h2>LinkedIn Connection Failed</h2>
        <p>Error: {error_description or error}</p>
        <p>Please close this window and try again.</p>
        <script>
            if (window.opener) {{
                window.opener.postMessage({{ type: 'linkedin-auth-error', error: '{error_description or error}' }}, '*');
                setTimeout(() => window.close(), 3000);
            }}
        </script>
        </body></html>
        """, status_code=200)

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")

    # Validate state from MongoDB
    state_doc = await db.oauth_states.find_one({"state": state})
    if not state_doc:
        raise HTTPException(status_code=400, detail="Invalid state parameter - possible CSRF attack")

    await db.oauth_states.delete_one({"state": state})
    if state_doc.get("used"):
        raise HTTPException(status_code=400, detail="State token already used")
    if time.time() - state_doc["created_at"] > 600:
        raise HTTPException(status_code=400, detail="State token expired")

    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as http_client:
            token_response = await http_client.post(
                LINKEDIN_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": LINKEDIN_CLIENT_ID,
                    "client_secret": LINKEDIN_CLIENT_SECRET,
                    "redirect_uri": LINKEDIN_REDIRECT_URI
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

        if token_response.status_code != 200:
            error_data = token_response.json()
            logger.error(f"Token exchange failed: {error_data}")
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {error_data.get('error_description', 'Unknown')}")

        token_data = token_response.json()
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 5184000)
        refresh_token = token_data.get("refresh_token")

        # Get user profile
        async with httpx.AsyncClient() as http_client:
            profile_response = await http_client.get(
                LINKEDIN_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )

        if profile_response.status_code != 200:
            logger.error(f"Profile fetch failed: {profile_response.text}")
            raise HTTPException(status_code=400, detail="Failed to fetch LinkedIn profile")

        profile = profile_response.json()
        linkedin_id = profile.get("sub")
        name = profile.get("name", "Unknown")
        email = profile.get("email")
        picture = profile.get("picture")

        person_urn = f"urn:li:person:{linkedin_id}"

        # Store account in DB
        account_id = str(uuid.uuid4())
        account_doc = {
            "account_id": account_id,
            "linkedin_id": linkedin_id,
            "person_urn": person_urn,
            "name": name,
            "email": email,
            "picture": picture,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": time.time() + expires_in,
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "last_sync_status": "connected",
            "last_sync_at": datetime.now(timezone.utc).isoformat(),
            "posting_target": "profile",
            "selected_company": None,
            "schedule_enabled": False,
            "schedule_interval_hours": 4
        }

        # Check if account already exists for this linkedin_id
        existing = await db.linkedin_accounts.find_one({"linkedin_id": linkedin_id})
        if existing:
            await db.linkedin_accounts.update_one(
                {"linkedin_id": linkedin_id},
                {"$set": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_expires_at": time.time() + expires_in,
                    "last_sync_status": "connected",
                    "last_sync_at": datetime.now(timezone.utc).isoformat(),
                    "name": name,
                    "email": email,
                    "picture": picture
                }}
            )
            account_id = existing["account_id"]
        else:
            await db.linkedin_accounts.insert_one(account_doc)

        logger.info(f"LinkedIn account connected: {name} ({linkedin_id})")

        # Return HTML that communicates back to parent window
        return HTMLResponse(content=f"""
        <html><body>
        <h2>LinkedIn Connected Successfully!</h2>
        <p>Welcome, {name}! You can close this window.</p>
        <script>
            if (window.opener) {{
                window.opener.postMessage({{
                    type: 'linkedin-auth-success',
                    account_id: '{account_id}',
                    name: '{name}',
                    linkedin_id: '{linkedin_id}'
                }}, '*');
                setTimeout(() => window.close(), 2000);
            }}
        </script>
        </body></html>
        """, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LinkedIn callback error: {e}")
        return HTMLResponse(content=f"""
        <html><body>
        <h2>Connection Error</h2>
        <p>{str(e)}</p>
        <script>
            if (window.opener) {{
                window.opener.postMessage({{ type: 'linkedin-auth-error', error: '{str(e)}' }}, '*');
                setTimeout(() => window.close(), 3000);
            }}
        </script>
        </body></html>
        """, status_code=200)


# ============== Account Management ==============
@router.get("/accounts")
async def get_linkedin_accounts():
    """Get all connected LinkedIn accounts."""
    accounts = await db.linkedin_accounts.find(
        {}, {"_id": 0, "access_token": 0, "refresh_token": 0}
    ).to_list(20)
    return {"accounts": accounts}


@router.delete("/accounts/{account_id}")
async def disconnect_linkedin_account(account_id: str):
    """Disconnect a LinkedIn account."""
    result = await db.linkedin_accounts.delete_one({"account_id": account_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"message": "Account disconnected"}


@router.put("/accounts/{account_id}/company")
async def set_account_company(account_id: str, company: str = Query(...)):
    """Set the active company context for a LinkedIn account."""
    if company not in COMPANY_CONTEXTS:
        raise HTTPException(status_code=400, detail=f"Unknown company: {company}. Valid: {list(COMPANY_CONTEXTS.keys())}")

    result = await db.linkedin_accounts.update_one(
        {"account_id": account_id},
        {"$set": {"selected_company": company}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"message": f"Company set to {company}"}


# ============== Token Refresh Helper ==============
async def get_valid_token(account_id: str) -> tuple:
    """Get a valid access token, refreshing if needed. Returns (access_token, person_urn)."""
    account = await db.linkedin_accounts.find_one({"account_id": account_id})
    if not account:
        raise HTTPException(status_code=404, detail="LinkedIn account not found")

    access_token = account["access_token"]
    expires_at = account.get("token_expires_at", 0)

    # If token expires in less than 1 day, try refresh
    if time.time() > expires_at - 86400:
        refresh_token = account.get("refresh_token")
        if refresh_token:
            try:
                async with httpx.AsyncClient() as http_client:
                    resp = await http_client.post(
                        LINKEDIN_TOKEN_URL,
                        data={
                            "grant_type": "refresh_token",
                            "refresh_token": refresh_token,
                            "client_id": LINKEDIN_CLIENT_ID,
                            "client_secret": LINKEDIN_CLIENT_SECRET
                        }
                    )
                if resp.status_code == 200:
                    token_data = resp.json()
                    access_token = token_data["access_token"]
                    new_refresh = token_data.get("refresh_token", refresh_token)
                    new_expires = time.time() + token_data.get("expires_in", 5184000)
                    await db.linkedin_accounts.update_one(
                        {"account_id": account_id},
                        {"$set": {
                            "access_token": access_token,
                            "refresh_token": new_refresh,
                            "token_expires_at": new_expires,
                            "last_sync_status": "token_refreshed",
                            "last_sync_at": datetime.now(timezone.utc).isoformat()
                        }}
                    )
                    logger.info(f"Token refreshed for account {account_id}")
                else:
                    logger.warning(f"Token refresh failed: {resp.text}")
            except Exception as e:
                logger.warning(f"Token refresh error: {e}")

        # If expired and refresh failed
        if time.time() > expires_at:
            await db.linkedin_accounts.update_one(
                {"account_id": account_id},
                {"$set": {"last_sync_status": "token_expired"}}
            )
            raise HTTPException(status_code=401, detail="LinkedIn token expired. Please reconnect.")

    return access_token, account["person_urn"]


# ============== Posting ==============
@router.post("/post")
async def create_linkedin_post(request: LinkedInPostRequest):
    """Post content to LinkedIn personal profile."""
    access_token, person_urn = await get_valid_token(request.account_id)

    # Build payload based on post type
    payload = {
        "author": person_urn,
        "commentary": request.content,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False
    }

    # Add link content if provided
    if request.post_type == "link" and request.link_url:
        payload["content"] = {
            "article": {
                "source": request.link_url,
                "title": request.link_title or "",
                "description": ""
            }
        }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": LINKEDIN_API_VERSION
    }

    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                LINKEDIN_POSTS_URL,
                json=payload,
                headers=headers
            )

        response_text = response.text
        post_id = response.headers.get("x-restli-id", "")

        if response.status_code not in [200, 201]:
            # Parse error for user-friendly message
            error_msg = response_text
            try:
                err_json = response.json()
                error_msg = err_json.get("message", response_text)
                if "REVOKED_ACCESS_TOKEN" in str(err_json):
                    error_msg = "Access token revoked. Please reconnect LinkedIn."
                elif "NOT_ENOUGH_PERMISSIONS" in str(err_json):
                    error_msg = "Insufficient permissions. Your LinkedIn app needs w_member_social scope."
            except Exception:
                pass

            logger.error(f"LinkedIn post failed [{response.status_code}]: {error_msg}")

            await db.linkedin_accounts.update_one(
                {"account_id": request.account_id},
                {"$set": {"last_sync_status": f"post_failed: {error_msg[:100]}", "last_sync_at": datetime.now(timezone.utc).isoformat()}}
            )
            raise HTTPException(status_code=response.status_code, detail=error_msg)

        # Save post record
        post_record = {
            "post_id": post_id,
            "account_id": request.account_id,
            "company": request.company,
            "content": request.content,
            "post_type": request.post_type,
            "link_url": request.link_url,
            "status": "published",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "linkedin_response_code": response.status_code
        }
        await db.linkedin_posts.insert_one(post_record)

        await db.linkedin_accounts.update_one(
            {"account_id": request.account_id},
            {"$set": {"last_sync_status": "post_published", "last_sync_at": datetime.now(timezone.utc).isoformat()}}
        )

        logger.info(f"LinkedIn post published: {post_id}")
        return {"status": "published", "post_id": post_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LinkedIn post error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Content Generation ==============
@router.post("/generate-content")
async def generate_linkedin_content(request: ContentGenerateRequest):
    """Generate LinkedIn post content for a company using LLM."""
    company_key = request.company.lower()
    if company_key not in COMPANY_CONTEXTS:
        raise HTTPException(status_code=400, detail=f"Unknown company: {request.company}")

    ctx = COMPANY_CONTEXTS[company_key]
    llm_key = os.environ.get("EMERGENT_LLM_KEY")
    if not llm_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    posts = []
    for i in range(request.post_count):
        try:
            chat = LlmChat(
                api_key=llm_key,
                session_id=f"linkedin-{company_key}-{uuid.uuid4()}",
                system_message=f"""You are a LinkedIn content strategist for {ctx['name']}. 
Write engaging, professional LinkedIn posts that drive engagement and thought leadership.

Company: {ctx['name']}
Tagline: {ctx['tagline']}
Description: {ctx['description']}
Products: {', '.join(ctx['products'])}
Value Props: {', '.join(ctx['value_props'])}
Target Audience: {ctx['target_audience']}

RULES:
- Write in first person as a founder/leader sharing insights
- Be conversational yet professional - not corporate jargon
- Use short paragraphs (1-2 lines each) for readability
- Include a hook in the first line that grabs attention
- Add 2-3 relevant emojis (not overdo)
- End with a thought-provoking question or call-to-action
- Include 3-5 relevant hashtags at the end
- Post length: 150-300 words ideal
- Share real industry insights, trends, or lessons
- DO NOT sound like AI - sound like a real founder sharing genuine thoughts
- Mix between: industry insights, product updates, customer stories, thought leadership"""
            ).with_model("openai", "gpt-4o")

            topic_prompt = f"Topic focus: {request.topic}" if request.topic else "Choose a relevant trending topic in retail tech, mall industry, or data intelligence"

            user_msg = UserMessage(
                text=f"""Write a LinkedIn post for {ctx['name']}.
{topic_prompt}
Tone: {request.tone}
Use these hashtags where appropriate: {ctx['hashtags']}

Write ONLY the post content. No meta text like 'Here's a post...' - just the actual post."""
            )

            response = await chat.send_message(user_msg)
            posts.append({
                "content": response,
                "company": company_key,
                "generated_at": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.error(f"Content generation error: {e}")
            posts.append({"content": f"Error generating content: {str(e)}", "company": company_key, "error": True})

    return {"posts": posts}


# ============== Post History ==============
@router.get("/posts")
async def get_post_history(account_id: str = Query(None), company: str = Query(None), limit: int = 50):
    """Get LinkedIn post history."""
    query = {}
    if account_id:
        query["account_id"] = account_id
    if company:
        query["company"] = company

    posts = await db.linkedin_posts.find(
        query, {"_id": 0}
    ).sort("published_at", -1).to_list(limit)
    return {"posts": posts}


# ============== Scheduling ==============
@router.post("/schedule")
async def update_schedule(request: ScheduleRequest):
    """Enable/disable auto-posting schedule for an account."""
    account = await db.linkedin_accounts.find_one({"account_id": request.account_id})
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    await db.linkedin_accounts.update_one(
        {"account_id": request.account_id},
        {"$set": {
            "schedule_enabled": request.enabled,
            "schedule_interval_hours": request.interval_hours,
            "selected_company": request.company
        }}
    )

    status = "enabled" if request.enabled else "disabled"
    return {"message": f"Schedule {status} for {request.company} every {request.interval_hours}h"}


@router.get("/schedule/status")
async def get_schedule_status():
    """Get all active schedules."""
    schedules = await db.linkedin_accounts.find(
        {"schedule_enabled": True},
        {"_id": 0, "access_token": 0, "refresh_token": 0}
    ).to_list(20)
    return {"schedules": schedules}


# ============== HearClear Infographic Generation ==============
INFOGRAPHIC_DIR = Path(__file__).parent.parent / "uploads" / "infographics"
INFOGRAPHIC_DIR.mkdir(parents=True, exist_ok=True)

HEARCLEAR_UNIFIED_POST = """We're standing at the intersection of healthcare's biggest blind spot and India's largest untapped opportunity.

63 million Indians live with disabling hearing loss. Only 5-7% use hearing aids — compared to 30% in developed nations. Over 90% of this market is fragmented mom-and-pop shops with zero clinical standards.

HearClear is building India's largest organized hearing care network. Here's what makes us different:

THE VISION — 40+ clinics across North India today. Target: 500-600 clinics. We're not selling hearing aids — we're building a comprehensive hearing care institution at scale.

AI-POWERED DIAGNOSTICS — Our proprietary AI test delivers 98% clinical-grade accuracy in just 8-10 minutes, replacing the traditional 45-minute soundproof booth test. We screen 10x more patients daily and catch hearing loss earlier than anyone else.

ECOSYSTEM INTEGRATION — Narayana Health, MAX@Home, EMOHA, 2050 Healthcare, and Healthians already partner with us. We embed into their operations as their audiology department — creating powerful referral loops.

CLINICAL DEPTH — With 100+ audiologists (India's largest private team), full-spectrum diagnostics (PTA, Impedance, OAE, BERA), cochlear implant referrals, speech therapy, and tinnitus management — we're a clinical powerhouse, not a retail shop.

THE OPPORTUNITY — India's hearing care market is $2B+, growing 15% YoY. WHO has proven the direct link between hearing loss and 5x higher dementia risk. India's aging population makes this urgent.

JOIN US — Whether you're an ENT specialist, hospital CEO, audiologist, healthcare partner, or investor — let's build India's hearing care revolution together.

DM me or comment below. Let's build this together.

#HearingCareRevolution #HealthcareTransformation #India2030 #InvestInHealth #HearClearGrowth #AIInHealthCare #ClinicalExcellence"""


# ============== 8 Distinct Infographic Themes ==============
HEARCLEAR_INFOGRAPHIC_THEMES = [
    {
        "slug": "market-disruptor",
        "title": "The Market Disruptor",
        "subtitle": "How HearClear is organizing India's fragmented hearing care industry",
        "system_message": "You are a BCG strategy consultant creating a market disruption infographic. Your style is bold, data-driven, with sharp contrasts showing before vs after states. Think Uber vs Taxis or Lenskart vs local opticians.",
        "prompt": """Create a striking corporate infographic titled "DISRUPTING A $2B UNORGANIZED MARKET"

DESIGN:
- Dark navy (#0B1929) background, electric gold (#FFD700) accents, white text
- Style: BCG strategy deck — bold headlines, sharp data callouts, comparison layout
- Layout: Split-screen / before-vs-after disruption narrative

CONTENT FLOW:
HEADER: "HearClear India — Organizing the Unorganized" in bold gold

LEFT SIDE — "INDIA'S HEARING CARE TODAY" (show as broken/fragmented):
- "90%+ market = mom-and-pop shops"
- "No standardized diagnostics"
- "45-minute outdated booth tests"
- "No follow-up care or rehabilitation"
- "Only 5-7% of 63M affected Indians get help"
- Visual metaphor: scattered, disconnected dots

RIGHT SIDE — "THE HEARCLEAR STANDARD" (show as connected/organized):
- "40+ clinics with uniform clinical protocols"
- "AI diagnostics: 98% accuracy in 8 minutes"
- "100+ audiologists — largest private team in India"
- "Full care continuum: diagnosis → fitting → rehabilitation → monitoring"
- "Embedded in Narayana Health, MAX, EMOHA ecosystem"
- Visual metaphor: connected network/nodes

BOTTOM BAR: "From fragmented retail to institutional healthcare. 500+ clinics by 2027. hearclearindia.com"

Make it look like a strategy consulting war-room slide. Bold, high-contrast, executive-grade.""",
        "post_content": """India's hearing care industry is stuck in the 1990s.

Over 90% of the market is run by mom-and-pop shops with no diagnostic standards, no clinical protocols, no rehabilitation, and no follow-up. A patient walks in, gets sold a device, and walks out. That's not healthcare — that's retail.

Meanwhile, 63 million Indians live with disabling hearing loss. Only 5-7% ever get a hearing aid. Compare that to 30% in developed nations. The gap isn't technology — it's infrastructure.

HearClear is changing the game entirely.

We've built 40+ clinics with standardized clinical protocols — the same experience whether you walk into our Jaipur clinic or our Delhi flagship. Our AI-powered diagnostics deliver 98% accuracy in 8 minutes, replacing the outdated 45-minute booth test that most of India still relies on.

With 100+ audiologists on our team — the largest private audiology force in India — we don't just fit devices. We diagnose, treat, rehabilitate, and monitor. Full-spectrum care that actually changes patient outcomes.

And we're not doing it alone. Narayana Health, MAX@Home, EMOHA, 2050 Healthcare, and Healthians are already embedded partners.

This is what organizing a $2B+ unorganized market looks like. From scattered shops to institutional healthcare.

500+ clinics by 2027. The disruption is underway.

#HearingCareRevolution #MarketDisruption #HealthcareInfrastructure #OrganizedHealthcare #HearClearIndia #StartupIndia"""
    },
    {
        "slug": "dementia-crisis",
        "title": "The Dementia Connection",
        "subtitle": "Why untreated hearing loss is India's silent dementia accelerator",
        "system_message": "You are a public health data visualization expert. You create emotionally impactful yet scientifically grounded infographics about health crises. Think WHO/Lancet report style — authoritative, urgent, backed by data.",
        "prompt": """Create a powerful public health infographic titled "THE SILENT LINK: HEARING LOSS & DEMENTIA IN INDIA"

DESIGN:
- Deep midnight blue (#091B2F) background with warm amber (#E8A838) and urgent coral-red accents
- Style: WHO/Lancet public health report — authoritative, data-rich, urgency-driven
- Layout: Top-down flow with large statistics and connecting visual lines showing causation

CONTENT:
HEADER: "India's Silent Health Crisis" — large, urgent typography

STAT BLOCK 1 (huge numbers): 
"63 MILLION Indians with hearing loss"
"5x higher risk of dementia" (WHO citation)
"Only 5-7% receive treatment"

THE CHAIN OF IMPACT (visual flow/cascade):
"Untreated Hearing Loss → Social Isolation → Cognitive Decline → Dementia"
"India has 5.3 million dementia patients — 3rd highest globally"
"By 2050: projected 14 million+"
"Cost to families: devastating. Cost to healthcare system: unsustainable."

HOW HEARCLEAR BREAKS THE CHAIN:
"Early AI screening catches loss 3x earlier"
"40+ accessible clinics across North India"
"Embedded in elder care: EMOHA, 2050 Healthcare partnerships"
"Full rehabilitation — not just a device sale"
"Goal: Screen 1 million Indians by 2028"

BOTTOM: "Every hearing aid fitted is a potential dementia case prevented. hearclearindia.com"

Make it feel like a Lancet editorial meets TED Talk — urgent, data-backed, emotionally resonant. Not corporate — humanitarian.""",
        "post_content": """This is the statistic that changed everything for us at HearClear:

Untreated hearing loss increases dementia risk by 5x. That's not a fringe study — that's the World Health Organization.

India has 63 million people with disabling hearing loss. Only 5-7% get any help. Meanwhile, we're the third-largest dementia population globally — 5.3 million and counting. By 2050, that number hits 14 million.

The connection is devastating and direct: untreated hearing loss → social isolation → cognitive decline → dementia. It's a chain we can break — but only if we act now.

This is why HearClear exists. Not to sell hearing aids. To prevent a public health catastrophe.

Our AI-powered screening catches hearing loss 3x earlier than traditional methods. Our 40+ clinics are embedded within elder care ecosystems — EMOHA, 2050 Healthcare — where we reach seniors before it's too late.

We don't just fit devices. We provide full rehabilitation — speech therapy, cognitive engagement, ongoing monitoring. Because a hearing aid in a drawer helps no one.

Our goal: screen 1 million Indians by 2028. Every early detection is potentially a dementia case prevented.

This isn't just healthcare. It's a moral imperative.

#HearingLossAndDementia #ElderCareIndia #PublicHealth #DementiaPrevention #HearClearIndia #WHO #AgingPopulation"""
    },
    {
        "slug": "ai-revolution",
        "title": "AI Diagnostic Revolution",
        "subtitle": "How AI is transforming hearing diagnostics from 45 minutes to 8 minutes",
        "system_message": "You are a tech-forward healthcare infographic designer specializing in AI/medtech visuals. Your style combines Silicon Valley tech aesthetics with medical precision — think Apple Health meets Stanford Medicine.",
        "prompt": """Create a sleek, tech-forward infographic titled "AI IS REWRITING THE RULES OF HEARING DIAGNOSTICS"

DESIGN:
- Dark gradient background (#0D1B2A to #1B3A5C) with bright teal (#00D4AA) and gold (#F0C75E) accents
- Style: Tech-medical crossover — clean, futuristic, data-visualization heavy
- Layout: Horizontal timeline/transformation showing old vs new, with circuit-board or neural-network visual elements

CONTENT:
HEADER: "The 8-Minute Revolution" — sleek, modern typography
SUBHEADER: "HearClear's AI Diagnostics vs. Traditional Hearing Tests"

COMPARISON (large, visual):
TRADITIONAL: "45 minutes | Soundproof booth required | Subjective interpretation | 1 patient/hour | Limited locations | Patients avoid it"
HEARCLEAR AI: "8 minutes | Any clinical setting | 98% objective accuracy | 10x more patients/day | Scalable to 500+ clinics | Patients welcome it"

IMPACT METRICS (bold callouts):
"10x throughput increase"
"3x earlier detection"  
"70% reduction in misdiagnosis"
"Deployed across 40+ clinics"

TECHNOLOGY STACK (visual):
"AI-Powered Audiometry → Real-time Analysis → Clinical-Grade Reports → Predictive Hearing Health"

FUTURE VISION:
"Next: Predictive hearing health | Remote monitoring | Personalized rehab protocols | AI-assisted device tuning"

BOTTOM: "The audiologist isn't replaced. The audiologist is supercharged. hearclearindia.com"

Make it feel like a product launch from a world-class health-tech company. Clean, modern, aspirational.""",
        "post_content": """The 45-minute soundproof booth hearing test was designed in the 1950s.

It requires specialized equipment, dedicated space, and a patient willing to sit still for nearly an hour. In a country where 63 million people need hearing evaluation, this approach was never going to scale.

At HearClear, we threw out the playbook.

Our AI-powered diagnostic delivers 98% clinical-grade accuracy in just 8 minutes. No soundproof booth required. Can be deployed in any clinical setting — a hospital, a clinic, even a home visit.

The numbers speak for themselves:
- 10x more patients screened per day
- 3x earlier detection of hearing loss
- 70% reduction in subjective misdiagnosis
- Already deployed across 40+ clinics

But here's what matters most: we didn't build this to replace audiologists. We built it to supercharge them.

Our 100+ audiologists now spend less time on routine testing and more time on what actually matters — patient counseling, device fitting, rehabilitation planning, and follow-up care.

The future we're building: predictive hearing health, remote monitoring, AI-assisted device tuning, and personalized rehabilitation protocols.

From 45 minutes to 8 minutes isn't just an efficiency gain. It's the difference between a patient who avoids testing and one who embraces it.

That's how you solve a 63-million-person problem.

#AIinHealthcare #HearingTech #HealthTechInnovation #AudiologyRevolution #HearClearAI #MedTech"""
    },
    {
        "slug": "ecosystem-flywheel",
        "title": "The Ecosystem Flywheel",
        "subtitle": "How HearClear built a referral network no competitor can replicate",
        "system_message": "You are a strategy consultant specializing in platform business models and ecosystem plays. You create visuals showing network effects, flywheels, and partnership moats — think Amazon flywheel or Jio ecosystem diagrams.",
        "prompt": """Create a strategic ecosystem infographic titled "THE HEARCLEAR FLYWHEEL: Healthcare Integration That Compounds"

DESIGN:
- Rich navy (#0A1930) background with emerald green (#00B87A) and gold (#D4A843) accents
- Style: Platform strategy / flywheel diagram — interconnected, showing momentum and reinforcement loops
- Layout: Central flywheel with radiating spokes to each partner type, showing how value flows between them

CONTENT:
HEADER: "Not a Clinic. An Ecosystem." — bold, strategic

CENTRAL FLYWHEEL (circular, showing reinforcing loop):
"Patient Trust → Referrals → Scale → Better Outcomes → More Trust"

PARTNER SPOKES (radiating from center, each with specific value exchange):

1. HOSPITALS — "Narayana Health, MAX@Home"
   "They get: Audiology department without the overhead"
   "We get: Patient access + credibility"

2. ELDER CARE — "EMOHA, 2050 Healthcare"
   "They get: Essential service for aging clients"
   "We get: Direct access to highest-need demographic"

3. PREVENTIVE HEALTH — "Healthians"
   "They get: Hearing screening added to health checkups"
   "We get: Early-stage detection pipeline"

4. ENT DOCTORS — "100+ referring ENTs"
   "They get: Reliable follow-through for their patients"
   "We get: Professional referral stream"

5. DEVICE BRANDS — "Signia, ReSound, Widex, Phonak, Oticon"
   "They get: Largest organized distribution in India"
   "We get: Best devices at scale pricing"

MOAT STATEMENT: "This ecosystem took years to build. A new entrant can copy our clinic — they can't copy our network."

BOTTOM: "40+ clinics. 5 strategic partnerships. 100+ ENT referrers. Growing daily. hearclearindia.com"

Make it feel like a Sequoia investment thesis slide — showing defensibility through network effects.""",
        "post_content": """In healthcare, you don't disrupt from outside. You integrate from within.

HearClear isn't trying to compete with hospitals. We're becoming their audiology department. We're not fighting ENTs for patients. We're their most trusted referral partner.

Here's the flywheel we've built — and why it's nearly impossible to replicate:

HOSPITALS: Narayana Health and MAX@Home get a fully-equipped audiology department without hiring a single audiologist or buying equipment. We handle everything. They gain a service line. We gain patient access and institutional credibility.

ELDER CARE: EMOHA and 2050 Healthcare serve India's growing elderly population. Hearing care is as essential as physiotherapy for their clients. We're embedded in their care protocols.

PREVENTIVE HEALTH: Healthians runs millions of health checkups annually. We've added hearing screening to their panel. Result: we catch hearing loss at stage 1, not stage 4.

ENTs: Over 100 ENT specialists refer patients to us because they trust our diagnostics and follow-through. We don't compete with them — we complete their care chain.

DEVICE PARTNERS: Signia, ReSound, Widex, Phonak, Oticon — the world's best hearing technology, available across our 40+ clinics at scale.

This is the moat. A new entrant can open a clinic tomorrow. They cannot build this network. Each partner reinforces the others. More hospitals → more patients → better outcomes → more referrals → more partners.

That's a flywheel. And it's accelerating.

#EcosystemStrategy #HealthcarePartnerships #NetworkEffects #HearClearIndia #StrategicMoat #PlatformBusiness"""
    },
    {
        "slug": "investor-thesis",
        "title": "The Investor Thesis",
        "subtitle": "Why HearClear is the Lenskart of hearing care — market data & growth trajectory",
        "system_message": "You are creating a Series B fundraising infographic for a top-tier VC pitch. Style: Sequoia/a16z pitch deck — all about TAM/SAM/SOM, growth curves, unit economics, and market timing. Clean, numbers-heavy, zero fluff.",
        "prompt": """Create an investor-grade infographic titled "THE INVESTMENT CASE FOR HEARCLEAR INDIA"

DESIGN:
- Dark charcoal (#111827) background with electric blue (#3B82F6) and gold (#F59E0B) accents
- Style: VC pitch deck — TAM/SAM/SOM circles, growth bar charts, metric callouts
- Layout: Structured grid with clear sections for market, traction, model, and vision

CONTENT:
HEADER: "HearClear India — Investment Thesis" in clean, authoritative font

MARKET SIZE (visual TAM/SAM/SOM circles):
"TAM: $2.5B — India hearing care market by 2030"
"SAM: $800M — organized clinical hearing care"
"SOM: $120M — current addressable with 500 clinics"

THE TIMING:
"India's 60+ population: 140M (2025) → 230M (2035)"
"Hearing aid penetration: 5% today vs 30% in developed markets"
"Government push: NPPCD + Ayushman Bharat coverage expanding"

TRACTION (bold metrics):
"40+ clinics operational"
"100+ audiologists employed"
"50,000+ patients served"
"5 strategic healthcare partnerships"
"AI diagnostics: 98% accuracy, 8-min test"
"Backed by Capgro Ventures"

BUSINESS MODEL (clean breakdown):
"Revenue: Device sales + Clinical services + B2B partnerships"
"Gross margins: ~50% on devices, ~70% on services"
"CAC payback: <6 months via partnership referrals"

THE COMP: "Lenskart organized eyecare ($4.5B). HearClear is organizing hearing care."

BOTTOM: "Target: 500+ clinics by 2027. India's hearing care is a $2.5B+ market waiting to be organized. hearclearindia.com"

Make it look like a real institutional investor presentation — zero emotion, all data, total credibility.""",
        "post_content": """Here's the investment thesis for hearing care in India in one post:

THE MARKET: India's hearing care market hits $2.5B+ by 2030. Today, hearing aid penetration is 5% — developed markets are at 30%. That's a 6x gap in a country with 63 million people needing help.

THE TIMING: India's 60+ population grows from 140M to 230M in the next decade. Government coverage is expanding through NPPCD and Ayushman Bharat. Awareness is finally rising.

THE PROBLEM: 90%+ of the market is unorganized. No clinical standards. No diagnostic protocols. No rehabilitation. Patients are sold devices, not healthcare.

THE COMPANY: HearClear has built what nobody else has:
- 40+ clinics with standardized protocols
- 100+ audiologists — India's largest private team
- AI diagnostics: 98% accuracy in 8 minutes
- 50,000+ patients served
- Embedded in Narayana Health, MAX, EMOHA, Healthians

THE MODEL: Device sales (~50% margins) + clinical services (~70% margins) + B2B partnership revenue. CAC payback under 6 months via institutional referrals.

THE COMP: Lenskart organized India's eyecare into a $4.5B company. Hearing care is the exact same playbook — fragmented market, aging demographics, technology-driven differentiation.

THE TARGET: 500+ clinics by 2027.

If you're looking at elder care, healthcare infrastructure, or India's demographic dividend — this is the bet.

#InvestInHealth #HealthcareInvesting #StartupIndia #ElderCare #HearClearIndia #VentureCapital #HealthTech"""
    },
    {
        "slug": "patient-experience",
        "title": "The New-Age Clinic Experience",
        "subtitle": "What a HearClear clinic visit actually looks like — reimagined from scratch",
        "system_message": "You are a customer experience design expert creating a patient journey infographic. Style: Apple retail experience meets Mayo Clinic — warm, human-centered, showing every touchpoint of a premium healthcare experience. Clean, inviting, aspirational.",
        "prompt": """Create a warm, premium infographic titled "HEARING CARE, REIMAGINED — The HearClear Patient Experience"

DESIGN:
- Warm navy (#152238) background with soft gold (#D4A843) and warm white accents
- Style: Premium service journey — Apple Store meets Mayo Clinic
- Layout: Step-by-step patient journey flowing left to right or top to bottom, each step as a distinct visual moment

CONTENT:
HEADER: "Not Your Father's Hearing Aid Shop" — warm, confident

THE OLD WAY (brief, crossed-out/faded):
"Dusty shop → 1 salesperson → hearing aid sale → goodbye"

THE HEARCLEAR JOURNEY (6 steps, each visually distinct):

STEP 1 — "WELCOME": "Modern, warm clinic environment. No hospital sterility. Designed for comfort."

STEP 2 — "AI SCREENING": "8-minute AI-powered test. No soundproof booth. Results explained in plain language."

STEP 3 — "EXPERT CONSULTATION": "Dedicated audiologist. Full diagnostic battery: PTA, OAE, BERA, Impedance. Not a sales pitch."

STEP 4 — "PERSONALIZED FITTING": "World-class devices (Signia, Phonak, ReSound). Custom-fit. Real-ear measurement. Not one-size-fits-all."

STEP 5 — "REHABILITATION": "Speech therapy. Auditory training. Family counseling. Tinnitus management. Real care."

STEP 6 — "LIFELONG RELATIONSHIP": "Regular follow-ups. Remote monitoring. Device adjustments. We don't disappear after the sale."

BOTTOM STAT: "50,000+ patients have experienced the difference. 40+ clinics. hearclearindia.com"

Make it feel inviting, premium, and fundamentally different from everything else in Indian hearing care.""",
        "post_content": """Walk into most hearing aid shops in India. Here's what you'll find:

A cramped room. One person who's both salesman and technician. A basic hearing test. And pressure to buy a device before you leave.

No diagnostics. No rehabilitation. No follow-up. No care.

Now walk into a HearClear clinic. It's a fundamentally different experience:

STEP 1 — A modern, comfortable environment designed for patients, not transactions.

STEP 2 — An 8-minute AI-powered hearing screening. No intimidating soundproof booth. Results explained in plain language you actually understand.

STEP 3 — A dedicated audiologist runs comprehensive diagnostics — PTA, OAE, BERA, Impedance. This isn't a sales consultation. It's clinical assessment.

STEP 4 — If you need a device, it's fitted with real-ear measurement using world-class brands (Signia, Phonak, ReSound). Custom-calibrated to your specific hearing profile.

STEP 5 — Rehabilitation begins. Speech therapy. Auditory training. Family counseling. Tinnitus management. Because a device without rehabilitation is a device in a drawer.

STEP 6 — The relationship doesn't end at purchase. Regular follow-ups, remote monitoring, device adjustments. We're there for life.

50,000+ patients have experienced this difference across our 40+ clinics.

This is what hearing care should have always been.

#PatientExperience #HearingCare #NewAgeHealthcare #CustomerFirst #HearClearIndia #HealthcareRedesigned"""
    },
    {
        "slug": "audiologist-army",
        "title": "India's Audiologist Army",
        "subtitle": "How HearClear built the largest private audiology team in the country",
        "system_message": "You are a talent/HR brand strategist creating a recruitment-meets-capability infographic. Style: LinkedIn employer branding — showing team strength, capability depth, and career opportunity. Inspiring, professional, team-focused.",
        "prompt": """Create a powerful team-capability infographic titled "100+ AUDIOLOGISTS. ONE MISSION. INDIA'S HEARING."

DESIGN:
- Deep blue (#0F1F3D) background with vibrant coral (#FF6B6B) and gold (#F0C75E) accents
- Style: Employer brand / capability showcase — people-focused, energetic, professional
- Layout: Central "100+" hero number with radiating capability spokes and team stats

CONTENT:
HEADER: "India's Largest Private Audiology Team" — bold, proud

HERO STAT: "100+" in massive typography with "Audiologists" below

CAPABILITY SPECTRUM (visual wheel/grid):
- "Pure Tone Audiometry (PTA)"
- "Otoacoustic Emissions (OAE)"
- "Brainstem Evoked Response (BERA)"
- "Impedance Audiometry"
- "Cochlear Implant Assessment"
- "Speech Therapy & Rehab"
- "Tinnitus Management"
- "Pediatric Audiology"
- "Vestibular Assessment"
- "Hearing Aid Fitting & REM"

WHY THIS MATTERS (3 callouts):
"You can't recruit 100 audiologists overnight — this took years of investment"
"90% of competitors have 1-3 audiologists per location"
"Our team IS the moat. Equipment can be bought. Expertise can't."

BRANDS WE WORK WITH: "Signia | ReSound | Widex | Phonak | Oticon"

HIRING BANNER: "We're always hiring. Join India's hearing care revolution."

BOTTOM: "40+ clinics. 50,000+ patients. Built on clinical excellence. hearclearindia.com"

Make it feel proud, energetic, and impossible to replicate.""",
        "post_content": """Here's a question for anyone trying to enter India's hearing care market:

Where are you going to find 100 qualified audiologists?

At HearClear, we've spent years building India's largest private audiology team. 100+ specialists trained across the full diagnostic and rehabilitation spectrum:

Pure Tone Audiometry. OAE. BERA. Impedance Testing. Cochlear Implant Assessment. Speech Therapy. Tinnitus Management. Pediatric Audiology. Vestibular Assessment. Real-Ear Measurement.

This isn't a sales team with a weeks training. These are clinical professionals who've chosen to build their careers at HearClear because we invest in their growth, give them world-class equipment (Signia, ReSound, Widex, Phonak, Oticon), and let them practice actual healthcare — not retail.

Here's the uncomfortable truth for our competitors: 90% of hearing aid shops in India have 1-3 people on staff. Many aren't even qualified audiologists. They're salespeople who learned on the job.

Equipment can be purchased. Clinic space can be rented. But building a team of 100+ clinical audiologists? That takes years of recruitment, training, retention, and culture-building.

This is our moat. And we're still hiring.

If you're an audiologist who wants to work with cutting-edge AI diagnostics, world-class devices, and a team that actually cares about patient outcomes — DM me.

50,000+ patients served. 40+ clinics. Built on clinical excellence, not sales targets.

#AudiologyCareers #ClinicalExcellence #HearClearIndia #HealthcareHiring #AudiologistArmy #HearingCare"""
    },
    {
        "slug": "india-crisis-map",
        "title": "India's Hearing Crisis by the Numbers",
        "subtitle": "A data-driven map of India's hearing health emergency",
        "system_message": "You are an investigative data journalist creating an infographic for The Economist or Financial Times. Style: Data journalism — maps, charts, stark comparisons, letting numbers tell the devastating story. Clean, factual, undeniable.",
        "prompt": """Create a data-journalism infographic titled "INDIA'S HEARING HEALTH EMERGENCY — BY THE NUMBERS"

DESIGN:
- Off-black (#0D0D0D) background with stark white text and red (#E53E3E) / gold (#F0C75E) accent data points
- Style: The Economist / Financial Times data journalism — stark, factual, chart-heavy
- Layout: Dashboard-style with multiple data visualizations arranged in a grid

CONTENT:
HEADER: "63 Million Reasons to Act" — stark, journalistic

DATA BLOCK 1 — THE SCALE:
"63M Indians with disabling hearing loss"
"India = 18% of global hearing loss burden"
"#1 in absolute numbers worldwide"

DATA BLOCK 2 — THE GAP (comparison chart):
"Hearing aid penetration:"
"Denmark: 42% | USA: 30% | UK: 28% | China: 12% | INDIA: 5%"

DATA BLOCK 3 — THE DEMOGRAPHICS:
"1 in 3 Indians over 60 has hearing difficulty"
"60+ population: 140M today → 230M by 2035"
"Rural access: 80% of hearing care is in metros"

DATA BLOCK 4 — THE COST OF INACTION:
"5x dementia risk (WHO)"
"3x depression risk"
"$1.6T global economic impact of untreated hearing loss"
"India's share: estimated $180B+ in lost productivity"

DATA BLOCK 5 — THE SOLUTION EMERGING:
"HearClear: 40+ clinics | 100+ audiologists | AI diagnostics"
"Market opportunity: $2.5B+ by 2030"
"Penetration potential: 5% → 15% = $600M+ incremental"

BOTTOM: "The data is clear. The need is urgent. The opportunity is massive. hearclearindia.com"

Make it feel like a Financial Times special report — letting raw data create the urgency.""",
        "post_content": """Let the numbers speak.

63 million Indians have disabling hearing loss. That's 18% of the global burden — the highest absolute number of any country on earth.

Now look at how we're handling it:

Hearing aid penetration rates:
Denmark: 42%
USA: 30%
UK: 28%
China: 12%
India: 5%

Five percent. In a country where 1 in 3 people over 60 has measurable hearing difficulty. Where 80% of hearing care infrastructure is concentrated in metros, leaving 800 million rural and semi-urban Indians with virtually zero access.

The cost of doing nothing:
- 5x higher dementia risk (WHO)
- 3x higher depression risk
- $180B+ estimated annual productivity loss
- India's 60+ population is growing from 140M to 230M by 2035

This isn't a niche problem. It's a national health emergency hiding in plain sight.

HearClear is building the infrastructure to address it: 40+ clinics, 100+ audiologists, AI-powered diagnostics that can screen 10x faster than traditional methods. Embedded in hospital and elder care ecosystems that reach patients where they are.

The market opportunity: $2.5B+ by 2030. Moving penetration from 5% to just 15% unlocks $600M+ in incremental demand.

The data is clear. The need is urgent. The moment is now.

#HearingHealth #PublicHealthCrisis #IndiaHealthcare #DataDriven #HearClearIndia #HealthcareAccess #63MillionReasons"""
    }
]


# In-memory job tracker for infographic generation
infographic_jobs = {}


def _run_infographic_generation(job_id: str, theme: dict, llm_key: str):
    """Background worker to generate infographic."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_async_generate_infographic(job_id, theme, llm_key))
    loop.close()


async def _async_generate_infographic(job_id: str, theme: dict, llm_key: str):
    """Async infographic generation."""
    try:
        session_id = f"hearclear-{theme['slug']}-{uuid.uuid4()}"
        chat = LlmChat(
            api_key=llm_key,
            session_id=session_id,
            system_message=theme["system_message"]
        )
        chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])

        msg = UserMessage(text=theme["prompt"])
        text_response, images = await chat.send_message_multimodal_response(msg)

        if not images or len(images) == 0:
            infographic_jobs[job_id]["status"] = "failed"
            infographic_jobs[job_id]["error"] = "No images generated"
            return

        image_data = base64.b64decode(images[0]['data'])
        filename = f"hearclear_{theme['slug']}_{uuid.uuid4().hex[:8]}.png"
        filepath = INFOGRAPHIC_DIR / filename
        with open(filepath, "wb") as f:
            f.write(image_data)

        infographic_jobs[job_id]["status"] = "completed"
        infographic_jobs[job_id]["image_url"] = f"/api/linkedin/infographic/{filename}"
        infographic_jobs[job_id]["download_url"] = f"/api/linkedin/infographic-download/{filename}"
        infographic_jobs[job_id]["theme"] = theme["title"]
        infographic_jobs[job_id]["post_content"] = theme["post_content"]
        infographic_jobs[job_id]["filename"] = filename

        logger.info(f"HearClear infographic [{theme['title']}] generated: {filename} ({len(image_data)} bytes)")

    except Exception as e:
        logger.error(f"Infographic generation error: {e}")
        infographic_jobs[job_id]["status"] = "failed"
        infographic_jobs[job_id]["error"] = str(e)


@router.post("/generate-hearclear-infographic")
async def generate_hearclear_infographic(theme_id: Optional[int] = None):
    """Start infographic generation as background job. Returns job_id to poll."""
    llm_key = os.environ.get("EMERGENT_LLM_KEY")
    if not llm_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    import random
    themes = HEARCLEAR_INFOGRAPHIC_THEMES
    if theme_id is not None and 0 <= theme_id < len(themes):
        theme = themes[theme_id]
    else:
        theme = random.choice(themes)

    job_id = str(uuid.uuid4())
    infographic_jobs[job_id] = {
        "status": "generating",
        "theme": theme["title"],
        "started_at": datetime.now(timezone.utc).isoformat()
    }

    thread = threading.Thread(target=_run_infographic_generation, args=(job_id, theme, llm_key), daemon=True)
    thread.start()

    return {"job_id": job_id, "theme": theme["title"], "status": "generating"}


@router.get("/generate-status/{job_id}")
async def get_infographic_status(job_id: str):
    """Poll for infographic generation status."""
    job = infographic_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/infographic-themes")
async def get_infographic_themes():
    """List available infographic themes."""
    return {"themes": [{"id": i, "title": t["title"], "slug": t["slug"], "subtitle": t["subtitle"]} for i, t in enumerate(HEARCLEAR_INFOGRAPHIC_THEMES)]}


@router.get("/infographic/{filename}")
async def serve_infographic(filename: str):
    """Serve a generated infographic image."""
    filepath = INFOGRAPHIC_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Infographic not found")
    return FileResponse(str(filepath), media_type="image/png")


@router.get("/infographic-download/{filename}")
async def download_infographic(filename: str):
    """Download a generated infographic as attachment."""
    filepath = INFOGRAPHIC_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Infographic not found")
    return FileResponse(
        str(filepath),
        media_type="image/png",
        filename=f"HearClear_{filename}",
        headers={"Content-Disposition": f'attachment; filename="HearClear_{filename}"'}
    )


@router.get("/infographics")
async def list_infographics():
    """List all saved HearClear infographics."""
    files = sorted(INFOGRAPHIC_DIR.glob("hearclear_*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in files:
        result.append({
            "filename": f.name,
            "url": f"/api/linkedin/infographic/{f.name}",
            "download_url": f"/api/linkedin/infographic-download/{f.name}",
            "created_at": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            "size_kb": round(f.stat().st_size / 1024, 1)
        })
    return {"infographics": result}


# ============== Companies ==============
@router.get("/companies")
async def get_companies():
    """Get available company profiles for content generation."""
    companies = []
    for key, ctx in COMPANY_CONTEXTS.items():
        companies.append({
            "id": key,
            "name": ctx["name"],
            "tagline": ctx["tagline"],
            "description": ctx["description"],
            "website": ctx["website"]
        })
    return {"companies": companies}
