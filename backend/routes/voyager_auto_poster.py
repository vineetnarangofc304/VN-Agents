"""
Voyager Auto-Poster: Generates AI content with infographics and posts via Voyager API.
Runs as a background task, 4 posts per day with pillar rotation.
Uses li_at cookie (no OAuth needed).
"""
import os
import uuid
import base64
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from emergentintegrations.llm.chat import LlmChat, UserMessage
import httpx

logger = logging.getLogger(__name__)

mongo_url = os.environ.get('MONGO_URL', '')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'test_database')]

EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
LOGO_PATH = Path(__file__).parent.parent / "uploads" / "fundle_logo.png"
INFOGRAPHIC_DIR = Path(__file__).parent.parent / "uploads" / "auto_infographics"
try:
    INFOGRAPHIC_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

WHATSAPP_CTA = "\n\nWant to see this in action for your business? Let's talk.\nWhatsApp: +91-9910530372"

# ==========================================
# FUNDLE DEEP CONTEXT (from fundle.ai website + live products)
# ==========================================
FUNDLE_CONTEXT = """COMPANY: Fundle.ai
TAGLINE: The AI Operating System for Modern Retail and Mall Enterprises
WEBSITE: fundle.ai
CBO: Abhinav Khanna (Ex-Paytm, 40 Under 40 Realty+)

WHAT FUNDLE DOES:
Fundle.ai connects customer intelligence, marketing, commerce, stores, tenants, properties and operations through one intelligent enterprise platform called Fundle Brain.

TWO PLATFORMS:
1. Fundle Retail AI — Connected retail growth engine: customer acquisition, loyalty, commerce, marketplaces, MBO networks, social media, content, organic growth
2. Fundle Mall AI — Intelligent mall ecosystem: tenant sales (ADSR), visitor engagement, property ops, advertising, loyalty, management intelligence

FUNDLE BRAIN (Intelligence Layer):
- Unified enterprise intelligence across POS, ERP, CRM, e-commerce, marketplaces, WhatsApp, payments
- 6-step cycle: Detect → Analyse → Predict → Recommend → Execute → Learn
- Every interaction generates intelligence, every insight triggers action

AI AGENTS (NOT chatbots — governed digital teammates):
- Loyalty Agent: Manages tiers, rewards logic, redemption journeys, personalisation
- Campaign Agent: Plans, builds, executes retention & acquisition campaigns end-to-end
- Analytics Agent: Answers business questions in natural language over enterprise data
- Lead Agent: Qualifies inbound leads, routes to stores, drives WhatsApp follow-ups
- Commerce Agent: E-commerce merchandising, personalised recos, cart recovery
- Marketplace Agent: Detects deductions, reconciles settlements, flags SKU anomalies
- MBO Agent: Monitors outlets for stock-outs, sales dips, inactive channels
- Social Agent: Plans content, drafts copy, publishes across channels
- Media Agent: Generates product videos, reels, banners, marketplace creatives
- SEO Agent: Discovers topics, drafts long-form, monitors indexation
- Customer Agent: Product discovery, orders, offers, loyalty on any channel
- Tenant Sales Agent: Chases missing sales, verifies daily submissions, escalates non-compliance

RETAIL AI FLYWHEEL (8 stages):
Acquire → Convert → Understand → Engage → Sell Everywhere → Operate → Create → Optimise

LIVE PRODUCTS:
- KAZO Rewards (kazoloyalty.fundlebrain.ai): Enterprise loyalty CRM for KAZO fashion brand with tiers, points, campaigns, store management
- Fundle Finance OS (kazob2b.fundlezone.com): Marketplace reconciliation — ingests Myntra reports, calculates commissions (173 rules), reconciles settlements, surfaces discrepancies
- ADSR: Automated Daily Sales Reporting for malls — POS + portal + file capture, like-for-like, trading density

BUSINESS OUTCOMES:
- Higher retention: predict churn, launch reactivation, measure incremental repeat revenue
- Better campaign ROI: AI selects cohort, channel, creative — measures true incrementality
- Improved lead conversion: every lead scored, routed, followed up on WhatsApp and in-store
- Marketplace profitability: deductions detected, claims filed, settlements reconciled
- Higher sales compliance for malls: missing sales chased, portal + POS reconciled
- Management visibility: one live briefing across sales, footfall, campaigns, advertising

INTEGRATIONS: SAP, Shopify, Salesforce, WhatsApp Business, Meta Ads, Google Ads, Razorpay, Amazon, Flipkart, Myntra, Ajio, Nykaa, Power BI, Snowflake, BigQuery

TARGET AUDIENCE: Retail CXOs, mall operators, D2C founders, franchise networks, multi-brand retail, shopping centre management"""

# ==========================================
# TOPIC PILLARS FOR AUTO-POSTING
# ==========================================
TOPIC_PILLARS = [
    "AI Loyalty Agent: How Fundle's AI Loyalty Agent replaces rule-based engines. It manages tiers, rewards, redemption journeys, hyper-personalisation. Predicts churn, launches reactivation, measures incremental repeat revenue. Reference KAZO Rewards as a live example. 30-40% LTV improvement.",
    "AI Lead Agent for Retail: How AI qualifies, scores, routes and follows up on every lead automatically on WhatsApp and in-store. First response in seconds not hours. 3-5x lead-to-conversion improvement. Fundle Lead Agent connects the full funnel.",
    "Enterprise AI Agents vs Chatbots: Why Fundle agents are NOT chatbots or copilots. They are governed digital teammates with permissions, memory, approval chains and audit trails. 12 specialised agents built for real retail workflows. Name specific agents.",
    "Fundle Brain Intelligence Layer: How it connects POS, ERP, CRM, e-commerce, marketplaces, WhatsApp, payments into one continuously learning system. 6-step cycle: Detect, Analyse, Predict, Recommend, Execute, Learn. From fragmented systems to coordinated intelligence.",
    "AI-Powered CRM & Campaign Agent: How AI transforms CRM from a data dump into an action engine. Campaign Agent plans, builds and executes campaigns end-to-end. AI selects cohort, channel, creative. Measures true incrementality, not vanity metrics.",
    "Retail AI Flywheel: Eight coordinated stages — Acquire, Convert, Understand, Engage, Sell Everywhere, Operate, Create, Optimise. Every interaction strengthens every other stage. Compounding growth.",
    "ADSR & Mall AI: How Automated Daily Sales Reporting and Mall AI transforms mall operations. Tenant sales tracking, visitor engagement, property ops, advertising monetisation. One connected mall OS instead of 20 disconnected systems.",
    "Marketplace Reconciliation: How Fundle Finance OS detects marketplace deductions, reconciles settlements to the paisa, flags SKU anomalies. 173 commission rules for Myntra alone. Brands losing 3-8% revenue to undetected deductions.",
    "AI Commerce Agent: How AI runs e-commerce merchandising, personalised recommendations, cart recovery, and marketplace operations. Selling everywhere from one intelligence layer — Shopify, Amazon, Flipkart, Myntra, Ajio.",
    "The ROI of Enterprise AI in Retail: Hard numbers — what happens when AI handles lead follow-up (seconds vs hours), campaign execution (hours vs weeks), loyalty personalisation (individual vs segment), marketplace reconciliation (automated vs manual). Unit economics of AI agents.",
]


async def _get_voyager_session():
    """Get li_at cookie + JSESSIONID for Voyager API."""
    cookie_doc = await db.li_search_config.find_one({"type": "cookie"})
    if not cookie_doc or not cookie_doc.get("li_at"):
        return None, None, None

    li_at = cookie_doc["li_at"]
    jsessionid = cookie_doc.get("jsessionid", "")

    if not jsessionid:
        # Auto-obtain JSESSIONID
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as c:
                resp = await c.get(
                    "https://www.linkedin.com/feed/",
                    headers={"cookie": f"li_at={li_at}", "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                for h in resp.headers.get_list("set-cookie"):
                    if "JSESSIONID" in h:
                        jsessionid = h.split(";")[0].split("=", 1)[1].strip('"')
                        await db.li_search_config.update_one({"type": "cookie"}, {"$set": {"jsessionid": jsessionid}})
                        break
        except Exception as e:
            logger.error(f"JSESSIONID obtain error: {e}")

    if not jsessionid:
        return None, None, None

    clean_js = jsessionid.strip('"').replace("ajax:", "")
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'accept': 'application/vnd.linkedin.normalized+json+2.1',
        'x-restli-protocol-version': '2.0.0',
        'content-type': 'application/json',
        'cookie': f'li_at={li_at}; JSESSIONID="ajax:{clean_js}"',
        'csrf-token': f'ajax:{clean_js}',
    }
    return li_at, clean_js, headers


async def _generate_post_content(pillar: str) -> str:
    """Generate a LinkedIn post using GPT-4o with deep Fundle context."""
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"auto-post-{uuid.uuid4()}",
        system_message=f"""You are Abhinav Khanna, Chief Business Officer at Fundle.ai.

{FUNDLE_CONTEXT}

WRITING STYLE:
- First person, founder/CBO voice — confident, insightful, never salesy
- Open with a provocative stat, bold claim, or counterintuitive insight
- Short paragraphs (1-3 lines max) for mobile readability
- Weave in REAL data points and industry benchmarks
- Reference specific AI agents by name (Loyalty Agent, Lead Agent, Campaign Agent etc.)
- Reference live products where relevant (KAZO Rewards, Fundle Finance OS, ADSR)
- Show deep domain knowledge — you've been in retail tech and worked at Paytm
- 150-300 words — punchy, not verbose
- 2-3 emojis max (subtle, not decorative)
- ALWAYS end with this EXACT CTA before hashtags:
  "Want to see this in action for your business? Let's talk.
  WhatsApp: +91-9910530372"
- Then 4-6 hashtags ALWAYS including #FundleAI #EnterpriseAI #RetailAI
- NEVER sound like AI. NEVER use "In today's rapidly evolving" or similar cliches.
- Don't name competitors. Focus on the problem and the Fundle approach."""
    ).with_model("openai", "gpt-4o")

    content = await chat.send_message(
        UserMessage(text=f"Write a LinkedIn post about: {pillar}\n\nWrite ONLY the post. No meta commentary.")
    )
    return content


async def _generate_infographic(content: str) -> str:
    """Generate an infographic using Gemini Nano Banana with actual Fundle logo."""
    try:
        # Read the actual Fundle logo
        logo_b64 = ""
        if LOGO_PATH.exists():
            with open(LOGO_PATH, "rb") as f:
                logo_b64 = base64.b64encode(f.read()).decode()

        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"auto-infographic-{uuid.uuid4()}",
            system_message="""You are a world-class brand designer creating vertical infographics for Fundle.ai's LinkedIn.

BRAND IDENTITY — FUNDLE.AI:
- Logo: The word "fundle" in rounded playful font. Each letter has a distinct color/icon: "f" has a fork icon (gray/red), "u" has a colorful curved path (red, yellow, teal sections), "n" has a purple shopping bag, "d" is gray, "l" is gray, "e" is gray with teal accent.
- Tagline: "Enterprise AI for Retail & Malls"
- Brand Colors: White/light gray background, with logo colors as accents (red/pink, yellow/gold, purple, teal). Clean modern look.
- Key message: Fundle.ai builds Enterprise AI Agents for Retail

INFOGRAPHIC RULES (MANDATORY):
1. Place the Fundle.ai logo text "fundle" prominently at the TOP — large, clear, unmissable. Use the brand's playful multi-colored style.
2. Tagline "Enterprise AI for Retail & Malls" below the logo.
3. Vertical format: 768x1376 pixels (LinkedIn-optimized).
4. Clean white or light background with colored accent sections.
5. Professional, data-driven, modern design. Think McKinsey meets Stripe.
6. Include 3-5 real data points with large bold numbers.
7. Reference specific AI Agents by name where relevant.
8. Icons or mini-charts for each data point.
9. Footer: "fundle.ai | WhatsApp: +91-9910530372" """
        )
        chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])

        prompt = f"""Create a striking vertical infographic (768x1376) for Fundle.ai.

Topic based on this LinkedIn post:
{content[:600]}

Include the Fundle logo at the top. Design a clean, professional infographic with 3-5 key stats.
Footer: fundle.ai | WhatsApp: +91-9910530372"""

        images_input = []
        if logo_b64:
            images_input = [f"data:image/png;base64,{logo_b64}"]

        msg = UserMessage(text=prompt, images=images_input) if images_input else UserMessage(text=prompt)
        text_resp, images = await chat.send_message_multimodal_response(msg)

        if images and len(images) > 0:
            image_data = base64.b64decode(images[0]['data'])
            filename = f"auto_{uuid.uuid4().hex[:8]}.png"
            filepath = INFOGRAPHIC_DIR / filename
            with open(filepath, "wb") as f:
                f.write(image_data)
            logger.info(f"Auto-infographic generated: {filename}")
            return str(filepath)
    except Exception as e:
        logger.error(f"Infographic generation error: {e}")
    return ""


async def _upload_and_post_voyager(headers: str, content: str, image_path: str) -> dict:
    """Upload image and post via Voyager API."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        media_urn = None

        # Upload image if available
        if image_path and os.path.exists(image_path):
            try:
                reg_resp = await client.post(
                    "https://www.linkedin.com/voyager/api/voyagerMediaUploadMetadata?action=upload",
                    json={"mediaUploadType": "IMAGE_SHARING", "fileSize": os.path.getsize(image_path), "filename": "infographic.png"},
                    headers=headers,
                )
                if reg_resp.status_code == 200:
                    reg_data = reg_resp.json()
                    upload_url = reg_data.get("data", {}).get("value", {}).get("singleUploadUrl", "")
                    media_urn = reg_data.get("data", {}).get("value", {}).get("urn", "")
                    if upload_url and media_urn:
                        with open(image_path, "rb") as f:
                            img_bytes = f.read()
                        up_headers = dict(headers)
                        up_headers['content-type'] = 'image/png'
                        await client.put(upload_url, content=img_bytes, headers=up_headers)
                        logger.info(f"Voyager image uploaded: {media_urn}")
            except Exception as e:
                logger.error(f"Image upload error: {e}")

        # Build post payload
        payload = {
            'visibleToConnectionsOnly': False,
            'externalAudienceProviders': [],
            'commentaryV2': {'text': content, 'attributes': []},
            'origin': 'FEED',
            'allowedCommentersScope': 'ALL',
            'postState': 'PUBLISHED',
        }
        if media_urn:
            payload['mediaCategory'] = 'IMAGE'
            payload['media'] = [{'category': 'IMAGE', 'mediaUrn': media_urn, 'tapTargets': []}]

        resp = await client.post(
            'https://www.linkedin.com/voyager/api/contentcreation/normShares',
            json=payload, headers=headers,
        )

        if resp.status_code in [200, 201]:
            d = resp.json()
            urn = d.get("data", {}).get("status", {}).get("urn", "")
            return {"success": True, "urn": urn}
        else:
            return {"success": False, "status": resp.status_code, "error": resp.text[:200]}


# ==========================================
# MAIN SCHEDULER
# ==========================================
async def run_voyager_auto_poster():
    """Background task: auto-generate and post 4 LinkedIn posts daily via Voyager API."""
    await asyncio.sleep(300)  # Wait 5 minutes for startup

    while True:
        try:
            if not EMERGENT_KEY:
                logger.warning("Voyager auto-poster: No EMERGENT_LLM_KEY configured")
                await asyncio.sleep(3600)
                continue

            # Check Voyager session
            li_at, jsession, headers = await _get_voyager_session()
            if not headers:
                logger.warning("Voyager auto-poster: No valid li_at cookie. Skipping.")
                await asyncio.sleep(3600)  # Check again in 1 hour
                continue

            # Check post count today
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            posts_today = await db.voyager_post_history.count_documents({
                "status": "published",
                "posted_at": {"$gte": today_start}
            })

            POSTS_PER_DAY = 4
            if posts_today >= POSTS_PER_DAY:
                logger.info(f"Voyager auto-poster: {posts_today}/{POSTS_PER_DAY} posts today. Done for today.")
                await asyncio.sleep(3600)  # Check again in 1 hour
                continue

            # Check time gap (spread posts ~6 hours apart)
            hours_between = 24 / POSTS_PER_DAY
            last_post = await db.voyager_post_history.find_one(
                {"status": "published"}, sort=[("posted_at", -1)]
            )
            if last_post and last_post.get("posted_at"):
                try:
                    last_dt = datetime.fromisoformat(last_post["posted_at"].replace("Z", "+00:00"))
                    hours_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
                    if hours_since < hours_between:
                        logger.info(f"Voyager auto-poster: Last post {hours_since:.1f}h ago, waiting for {hours_between}h gap.")
                        await asyncio.sleep(1800)  # Check again in 30 min
                        continue
                except Exception:
                    pass

            # Pick topic from rotation
            config = await db.auto_poster_config.find_one({"type": "voyager"})
            last_idx = config.get("last_pillar_index", -1) if config else -1
            next_idx = (last_idx + 1) % len(TOPIC_PILLARS)
            pillar = TOPIC_PILLARS[next_idx]

            logger.info(f"Voyager auto-poster: Generating post #{posts_today+1} | Pillar: {pillar[:60]}...")

            # Generate content
            try:
                content = await _generate_post_content(pillar)
            except Exception as e:
                logger.error(f"Voyager auto-poster content generation failed: {e}")
                await asyncio.sleep(1800)
                continue

            # Ensure CTA is present
            if "9910530372" not in content:
                content = content.rstrip() + WHATSAPP_CTA

            # Generate infographic
            image_path = ""
            try:
                image_path = await _generate_infographic(content)
            except Exception as e:
                logger.error(f"Voyager auto-poster infographic failed: {e}")

            # Post via Voyager
            result = await _upload_and_post_voyager(headers, content, image_path)

            if result.get("success"):
                logger.info(f"Voyager auto-poster: PUBLISHED! URN: {result.get('urn')}")
                await db.voyager_post_history.insert_one({
                    "post_urn": result.get("urn", ""),
                    "content": content,
                    "image_path": image_path,
                    "has_image": bool(image_path),
                    "pillar": pillar[:100],
                    "pillar_index": next_idx,
                    "posted_at": datetime.now(timezone.utc).isoformat(),
                    "status": "published",
                    "source": "voyager_auto",
                })
                # Update rotation
                await db.auto_poster_config.update_one(
                    {"type": "voyager"},
                    {"$set": {"last_pillar_index": next_idx, "last_posted_at": datetime.now(timezone.utc).isoformat()}},
                    upsert=True
                )
            else:
                logger.error(f"Voyager auto-poster: POST FAILED: {result}")
                if result.get("status") in [401, 403]:
                    logger.error("Voyager auto-poster: Cookie expired! Stopping until refreshed.")
                    await asyncio.sleep(3600 * 6)  # Wait 6 hours before retrying
                    continue

        except Exception as e:
            logger.error(f"Voyager auto-poster error: {e}")

        await asyncio.sleep(1800)  # Check every 30 minutes
