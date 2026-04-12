import os
import time
import httpx
import secrets
import logging
import uuid
import base64
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
    oauth_states[state] = {"created_at": time.time(), "used": False}

    scopes = "openid profile w_member_social"
    params = (
        f"response_type=code"
        f"&client_id={LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={LINKEDIN_REDIRECT_URI}"
        f"&state={state}"
        f"&scope={scopes}"
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

    # Validate state
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter - possible CSRF attack")

    state_data = oauth_states.pop(state)
    if state_data["used"]:
        raise HTTPException(status_code=400, detail="State token already used")
    if time.time() - state_data["created_at"] > 600:
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


@router.post("/generate-hearclear-infographic")
async def generate_hearclear_infographic():
    """Generate a unified Blue & Gold corporate infographic for HearClear using Nano Banana."""
    llm_key = os.environ.get("EMERGENT_LLM_KEY")
    if not llm_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    try:
        session_id = f"hearclear-infographic-{uuid.uuid4()}"
        chat = LlmChat(
            api_key=llm_key,
            session_id=session_id,
            system_message="You are a world-class corporate infographic designer. You produce clean, investor-grade one-pager visuals for Fortune 500 companies."
        )
        chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])

        prompt = """Create a professional corporate infographic one-pager for "HearClear India" — a hearing healthcare company.

DESIGN REQUIREMENTS:
- Color scheme: DEEP NAVY BLUE (#0A1628, #1B2D4F) as primary background with RICH GOLD (#D4A843, #F0C75E) as accent color
- Style: McKinsey / Deloitte / BCG consulting standard — clean, structured, data-driven, enterprise-grade
- Layout: Vertical one-pager format, structured in clear sections with dividers
- Typography: Bold section headers in gold, body text in white/light gray on blue background

CONTENT SECTIONS (top to bottom):

1. HEADER: "HearClear India" in large gold text, with tagline "Building India's Largest Organized Hearing Care Network" below in white

2. THE PROBLEM (with icon): "63M Indians with hearing loss | Only 5-7% use aids | 90%+ market is unorganized"

3. OUR SOLUTION (3 columns):
   - "40+ Clinics" across North India
   - "100+ Audiologists" — India's largest private team
   - "98% AI Accuracy" — 8-min diagnostic test

4. AI DIAGNOSTICS: "Proprietary AI replaces 45-min booth test with 8-min clinical-grade screening — 10x more patients daily"

5. ECOSYSTEM PARTNERS: Show logos/names in a row: "Narayana Health | MAX@Home | EMOHA | 2050 Healthcare | Healthians"

6. CLINICAL DEPTH: "Full spectrum: PTA, Impedance, OAE, BERA, Cochlear Implants, Speech Therapy, Tinnitus Management"

7. MARKET OPPORTUNITY: "$2B+ Market | 15% YoY Growth | WHO: Hearing loss = 5x dementia risk"

8. CALL TO ACTION: "ENTs | Hospitals | Audiologists | Investors — Join the Revolution" with website "hearclearindia.com"

Make it look like a real McKinsey client deck slide — sharp, professional, investment-grade. No cartoons, no clipart."""

        msg = UserMessage(text=prompt)
        text_response, images = await chat.send_message_multimodal_response(msg)

        if not images or len(images) == 0:
            logger.error(f"No images generated. Text response: {text_response[:200] if text_response else 'None'}")
            raise HTTPException(status_code=500, detail="Image generation returned no images")

        # Save the image
        image_data = base64.b64decode(images[0]['data'])
        filename = f"hearclear_unified_{uuid.uuid4().hex[:8]}.png"
        filepath = INFOGRAPHIC_DIR / filename
        with open(filepath, "wb") as f:
            f.write(image_data)

        logger.info(f"HearClear infographic generated: {filename} ({len(image_data)} bytes)")

        return {
            "status": "success",
            "image_url": f"/api/linkedin/infographic/{filename}",
            "post_content": HEARCLEAR_UNIFIED_POST,
            "text_response": text_response[:500] if text_response else ""
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Infographic generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/infographic/{filename}")
async def serve_infographic(filename: str):
    """Serve a generated infographic image."""
    filepath = INFOGRAPHIC_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Infographic not found")
    return FileResponse(str(filepath), media_type="image/png")


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
