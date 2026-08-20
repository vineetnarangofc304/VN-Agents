"""
One-shot LinkedIn poster with infographic upload via Voyager API.
Run: python3 post_with_images.py <li_at> <jsessionid>
"""
import httpx
import asyncio
import json
import sys
import os

LI_AT = sys.argv[1] if len(sys.argv) > 1 else ""
JSESSION = sys.argv[2] if len(sys.argv) > 2 else ""

WHATSAPP_CTA = "\n\nWant to see this in action for your business? Let's talk.\nWhatsApp: +91-9910530372"

def build_headers():
    return {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'accept': 'application/vnd.linkedin.normalized+json+2.1',
        'x-restli-protocol-version': '2.0.0',
        'content-type': 'application/json',
        'cookie': f'li_at={LI_AT}; JSESSIONID="ajax:{JSESSION}"',
        'csrf-token': f'ajax:{JSESSION}',
    }

async def upload_image(client, image_path, headers):
    """Upload image via Voyager media upload and return the media URN."""
    # Step 1: Register upload
    register_payload = {
        "mediaUploadType": "IMAGE_SHARING",
        "fileSize": os.path.getsize(image_path),
        "filename": os.path.basename(image_path),
    }
    resp = await client.post(
        "https://www.linkedin.com/voyager/api/voyagerMediaUploadMetadata?action=upload",
        json=register_payload,
        headers=headers,
    )
    if resp.status_code not in [200, 201]:
        print(f"  Upload register failed: {resp.status_code} {resp.text[:200]}")
        return None
    
    data = resp.json()
    upload_url = data.get("value", {}).get("singleUploadUrl", "")
    media_urn = data.get("value", {}).get("urn", "")
    
    if not upload_url:
        # Try different response structure
        upload_url = data.get("data", {}).get("value", {}).get("singleUploadUrl", "")
        media_urn = data.get("data", {}).get("value", {}).get("urn", "")
    
    if not upload_url:
        print(f"  No upload URL in response: {json.dumps(data)[:300]}")
        return None
    
    print(f"  Upload URL obtained, media URN: {media_urn}")
    
    # Step 2: Upload the image binary
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    
    upload_headers = {
        'cookie': f'li_at={LI_AT}; JSESSIONID="ajax:{JSESSION}"',
        'csrf-token': f'ajax:{JSESSION}',
        'user-agent': headers['user-agent'],
        'content-type': 'image/png',
    }
    
    resp2 = await client.put(upload_url, content=image_bytes, headers=upload_headers)
    print(f"  Upload status: {resp2.status_code}")
    
    if resp2.status_code in [200, 201]:
        return media_urn
    return None


async def post_with_image(client, content, image_path, headers, post_num):
    """Generate content, upload image, and post."""
    print(f"\n{'='*50}")
    print(f"POST {post_num}")
    print(f"{'='*50}")
    
    # Ensure CTA is in content
    if "9910530372" not in content:
        content = content.rstrip() + WHATSAPP_CTA
    
    # Upload image
    media_urn = None
    if image_path and os.path.exists(image_path):
        print(f"  Uploading infographic: {os.path.basename(image_path)}")
        media_urn = await upload_image(client, image_path, headers)
    
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
        payload['media'] = [{'mediaUrn': media_urn, 'altText': 'Fundle.ai Infographic'}]
    
    # Post
    resp = await client.post(
        'https://www.linkedin.com/voyager/api/contentcreation/normShares',
        json=payload,
        headers=headers,
    )
    
    if resp.status_code in [200, 201]:
        d = resp.json()
        urn = d.get("data", {}).get("status", {}).get("urn", "")
        print(f"  PUBLISHED! URN: {urn}")
        return True
    else:
        print(f"  FAILED: {resp.status_code} {resp.text[:300]}")
        return False


async def main():
    if not LI_AT or not JSESSION:
        print("Usage: python3 post_with_images.py <li_at> <jsessionid>")
        return
    
    headers = build_headers()
    
    # Pre-generated content with CTA
    posts = [
        {
            "content": """What if your loyalty program could predict customer churn before it happens?

Most rule-based loyalty engines react to behaviour that already occurred. By the time a customer stops visiting, the damage is done.

At Fundle.ai, our AI Loyalty Agent flips this script. Instead of static tier rules and generic earn-burn mechanics, it continuously learns from every transaction, visit pattern, and engagement signal.

The result:
- Dynamic tier management that adapts in real-time
- Hyper-personalised reward recommendations per individual
- Churn prediction with proactive reactivation campaigns
- Measurable incremental repeat revenue, not vanity metrics

We are seeing 30-40% LTV improvement in brands that switch from rule-based to AI-driven loyalty.

The question is not whether AI agents will replace legacy loyalty engines. It is how fast your competitors will make the switch.

Want to see this in action for your retail business? Let's talk.
WhatsApp: +91-9910530372

#FundleAI #EnterpriseAI #RetailAI #LoyaltyAI #RetailTech #AIAgents""",
            "image": "/app/backend/uploads/company_infographics/69021406_629c7286.png"
        },
        {
            "content": """Responding to a lead within 5 minutes makes you 100x more likely to make contact.

Yet the average retail brand takes 47 hours.

This is where Fundle.ai's AI Lead Agent changes everything. Every inbound lead is instantly qualified, scored, routed to the right store or team, and followed up automatically on WhatsApp and in-store.

No lead falls through the cracks. No human delay. No missed opportunity.

What we are seeing with AI-powered lead management:
- 3-5x improvement in lead-to-conversion rates
- First response in seconds, not hours
- Automated WhatsApp follow-ups with personalised context
- Full funnel visibility from discovery to close

The brands winning in 2026 are not just generating more leads. They are converting the ones they already have, faster than humanly possible.

Ready to turn every lead into a customer? Let's talk.
WhatsApp: +91-9910530372

#FundleAI #EnterpriseAI #RetailAI #LeadGen #RetailTech #AIAgents""",
            "image": "/app/backend/uploads/company_infographics/69021406_b0724c8e.png"
        },
        {
            "content": """Your CRM is not a strategy. It is a data dump.

Most retail CRMs collect mountains of customer data but do nothing intelligent with it. Reports nobody reads. Segments nobody acts on. Follow-ups that happen too late.

Fundle Brain, our intelligence layer, transforms CRM from passive storage into an active revenue engine:

- AI-powered customer segmentation that updates in real-time
- Next-best-action recommendations for every customer touchpoint
- Cohort-based campaigns that AI plans, builds, and executes end-to-end
- Automated WhatsApp follow-ups triggered by predicted intent, not manual rules

The difference? Every interaction generates intelligence. Every insight triggers action. Every campaign measures true incrementality, not vanity metrics.

When AI handles your CRM, it stops being a cost center and becomes your highest-ROI channel.

Want AI-powered CRM for your retail business? Let's talk.
WhatsApp: +91-9910530372

#FundleAI #EnterpriseAI #RetailAI #CRM #MarketingAI #AIAgents""",
            "image": "/app/backend/uploads/company_infographics/69021406_eb953560.png"
        }
    ]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, post in enumerate(posts):
            success = await post_with_image(client, post["content"], post["image"], headers, i+1)
            if not success:
                print(f"\nPost {i+1} failed. Stopping to preserve cookie.")
                break
            if i < len(posts) - 1:
                await asyncio.sleep(5)  # Brief pause between posts
    
    print("\nDone!")

asyncio.run(main())
