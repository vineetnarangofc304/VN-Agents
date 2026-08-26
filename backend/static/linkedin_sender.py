#!/usr/bin/env python3
"""
LinkedIn CRM — Local Sender
Run this on your Mac/PC to send LinkedIn messages & connection requests.
Uses YOUR browser's cookie (same IP = no blocking by LinkedIn).

Setup:
  pip install requests

Usage:
  python linkedin_sender.py

It will:
  1. Log you into the CRM
  2. Pull pending prospects from your active campaigns
  3. Send invites/messages using your LinkedIn cookie
  4. Report status back to the CRM dashboard
  5. Wait 30s between sends, stop at daily limit
"""

import os
import sys
import json
import time
import uuid
import random
import string
import getpass
import requests
from datetime import datetime

# ============ CONFIG ============
CRM_URL = os.environ.get("CRM_URL", "https://vnagents.agenticindia.ai")
DELAY_MIN = 25  # seconds between sends
DELAY_MAX = 40
BATCH_SIZE = 25  # max sends per run

# ============ COLORS ============
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


def log(msg, color=RESET):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {msg}{RESET}")


def generate_tracking_id():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=16))


class LinkedInSender:
    def __init__(self):
        self.session = requests.Session()
        self.crm_token = None
        self.user = None
        self.li_at = ""
        self.jsessionid = ""

    def login_crm(self):
        """Login to CRM and get auth token."""
        print(f"\n{BOLD}{'='*50}")
        print(f"  LinkedIn CRM — Local Sender")
        print(f"  Server: {CRM_URL}")
        print(f"{'='*50}{RESET}\n")

        email = input(f"{BLUE}Email: {RESET}").strip()
        password = getpass.getpass(f"{BLUE}Password: {RESET}")

        resp = self.session.post(
            f"{CRM_URL}/api/crm-auth/login",
            json={"email": email, "password": password},
            timeout=15,
        )
        if resp.status_code != 200:
            log(f"Login failed: {resp.json().get('detail', resp.text[:100])}", RED)
            sys.exit(1)

        data = resp.json()
        self.crm_token = data.get("token", "")
        self.user = data
        self.session.headers["Authorization"] = f"Bearer {self.crm_token}"
        log(f"Logged in as {data.get('name')} ({data.get('role')})", GREEN)

    def get_cookies(self):
        """Get LinkedIn cookies — from CRM settings or ask user."""
        # Try getting from CRM settings
        resp = self.session.get(f"{CRM_URL}/api/crm/settings", timeout=10)
        if resp.status_code == 200:
            settings = resp.json()
            if settings.get("has_cookie"):
                log("LinkedIn cookies found in CRM settings", GREEN)
                use_saved = input(f"{BLUE}Use saved cookies? (y/n): {RESET}").strip().lower()
                if use_saved == "y":
                    # Get full cookies from CRM (need to fetch from user profile)
                    pass

        # Ask for cookies
        print(f"\n{YELLOW}To get your LinkedIn cookies:{RESET}")
        print("  1. Open LinkedIn in Chrome")
        print("  2. Press F12 → Application → Cookies → linkedin.com")
        print("  3. Copy 'li_at' value")
        print("  4. Copy 'JSESSIONID' value\n")

        self.li_at = input(f"{BLUE}li_at: {RESET}").strip()
        self.jsessionid = input(f"{BLUE}JSESSIONID: {RESET}").strip()

        if not self.li_at:
            log("li_at is required", RED)
            sys.exit(1)

        # Clean JSESSIONID
        self.jsessionid = self.jsessionid.replace('"', "").replace("ajax:", "")

        # Verify cookie works
        log("Verifying LinkedIn cookie...", YELLOW)
        headers = self._build_headers()
        r = requests.get(
            "https://www.linkedin.com/voyager/api/me",
            headers=headers, timeout=10, allow_redirects=False
        )
        if r.status_code == 200:
            log("LinkedIn cookie is valid!", GREEN)
        else:
            log(f"Cookie check returned {r.status_code} — it may not work", RED)
            cont = input(f"{BLUE}Continue anyway? (y/n): {RESET}").strip().lower()
            if cont != "y":
                sys.exit(1)

        # Save to CRM
        self.session.post(
            f"{CRM_URL}/api/crm/settings/cookie",
            json={"li_at": self.li_at, "jsessionid": f"ajax:{self.jsessionid}"},
            timeout=10,
        )

    def _build_headers(self):
        js = self.jsessionid
        return {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "x-restli-protocol-version": "2.0.0",
            "content-type": "application/json; charset=UTF-8",
            "cookie": f'li_at={self.li_at}; JSESSIONID="ajax:{js}"',
            "csrf-token": f"ajax:{js}",
        }

    def get_campaigns(self):
        """Fetch user's campaigns from CRM."""
        resp = self.session.get(f"{CRM_URL}/api/crm/campaigns", timeout=10)
        if resp.status_code != 200:
            log("Failed to fetch campaigns", RED)
            return []
        return resp.json().get("campaigns", [])

    def get_campaign_prospects(self, campaign_id):
        """Fetch campaign with prospects."""
        resp = self.session.get(f"{CRM_URL}/api/crm/campaigns/{campaign_id}", timeout=10)
        if resp.status_code != 200:
            return None
        return resp.json()

    def update_prospect_status(self, campaign_id, public_id, status, send_type=None, error=None):
        """Report prospect status back to CRM."""
        # Direct DB update not available from local — use a status endpoint
        # We'll use the retry endpoint for failures and mark sent via a new endpoint
        pass  # Will be handled by the send endpoint

    def resolve_urn(self, public_id, headers):
        """Resolve LinkedIn public_id to URN."""
        try:
            r = requests.get(
                f"https://www.linkedin.com/voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity={public_id}",
                headers=headers, timeout=15, allow_redirects=False,
            )
            if r.status_code == 200:
                for item in r.json().get("included", []):
                    urn = item.get("entityUrn", "")
                    if "fsd_profile" in urn:
                        return urn
        except Exception:
            pass
        return None

    def send_message(self, headers, member_id, message):
        """Send direct message to a 1st-degree connection."""
        tracking = generate_tracking_id()
        payload = {
            "keyVersion": "LEGACY_INBOX",
            "conversationCreate": {
                "eventCreate": {
                    "originToken": str(uuid.uuid4()),
                    "value": {
                        "com.linkedin.voyager.messaging.create.MessageCreate": {
                            "body": message,
                            "attributedBody": {"text": message, "attributes": []},
                            "attachments": [],
                        }
                    },
                    "trackingId": tracking,
                },
                "dedupeByClientGeneratedToken": False,
                "recipients": [member_id],
                "subtype": "MEMBER_TO_MEMBER",
            }
        }
        r = requests.post(
            "https://www.linkedin.com/voyager/api/messaging/conversations?action=create",
            json=payload, headers=headers, timeout=15, allow_redirects=False,
        )
        return r.status_code in [200, 201], r.status_code

    def send_invite(self, headers, urn, public_id, note):
        """Send connection request. Tries URN first, then public_id fallback."""
        note = note[:300]

        # Try verifyQuotaAndCreate with URN
        if urn:
            payload = {
                "inviteeProfileUrn": urn,
                "customMessage": note,
                "trackingId": str(uuid.uuid4()),
            }
            r = requests.post(
                "https://www.linkedin.com/voyager/api/voyagerRelationshipsDashMemberRelationships?action=verifyQuotaAndCreate",
                json=payload, headers=headers, timeout=15, allow_redirects=False,
            )
            if r.status_code in [200, 201]:
                return True, "invite_sent"
            if r.status_code == 401:
                return False, "cookie_expired"

        # Fallback: normInvitations with public_id
        payload2 = {
            "trackingId": str(uuid.uuid4()),
            "message": note,
            "invitations": [],
            "excludeInvitations": [],
            "invitee": {
                "com.linkedin.voyager.growth.invitation.InviteeProfile": {
                    "profileId": public_id
                }
            }
        }
        r2 = requests.post(
            "https://www.linkedin.com/voyager/api/growth/normInvitations",
            json=payload2, headers=headers, timeout=15, allow_redirects=False,
        )
        if r2.status_code in [200, 201]:
            return True, "invite_sent"
        return False, f"failed_{r2.status_code}"

    def send_to_prospect(self, headers, prospect, direct_msg, invite_note):
        """Send to a single prospect. Returns (success, send_type)."""
        public_id = prospect["public_id"]
        name = (prospect.get("name") or "").split()[0] or "there"
        company = prospect.get("company") or "your company"
        title = prospect.get("title") or ""

        # Personalize
        msg = direct_msg.replace("{name}", name).replace("{company}", company).replace("{title}", title)
        note = invite_note.replace("{name}", name).replace("{company}", company).replace("{title}", title)

        # Resolve URN
        urn = self.resolve_urn(public_id, headers)

        # Try direct message first (if URN found)
        if urn:
            member_id = urn.split(":")[-1]
            ok, status = self.send_message(headers, member_id, msg)
            if ok:
                return True, "message_sent"

        # Fall back to connection request
        ok, send_type = self.send_invite(headers, urn, public_id, note)
        return ok, send_type

    def run(self):
        """Main loop — pick campaign, send pending prospects."""
        self.login_crm()
        self.get_cookies()

        campaigns = self.get_campaigns()
        if not campaigns:
            log("No campaigns found", YELLOW)
            return

        # Show campaigns
        print(f"\n{BOLD}Your Campaigns:{RESET}")
        for i, c in enumerate(campaigns):
            status_color = GREEN if c.get("status") == "active" else YELLOW
            print(f"  {i+1}. {c['name']} — {status_color}{c.get('pending', 0)} pending{RESET}, {c.get('sent', 0)} sent, {c.get('failed', 0)} failed")

        choice = input(f"\n{BLUE}Pick campaign number (or 'all' for all active): {RESET}").strip()

        if choice.lower() == "all":
            selected = [c for c in campaigns if c.get("status") == "active" and c.get("pending", 0) > 0]
        else:
            try:
                idx = int(choice) - 1
                selected = [campaigns[idx]]
            except (ValueError, IndexError):
                log("Invalid choice", RED)
                return

        if not selected:
            log("No campaigns with pending prospects", YELLOW)
            return

        headers = self._build_headers()
        total_sent = 0
        total_failed = 0

        for campaign in selected:
            cid = campaign["campaign_id"]
            log(f"\n{'='*40}", BOLD)
            log(f"Campaign: {campaign['name']}", BOLD)
            log(f"Pending: {campaign.get('pending', 0)}", BLUE)

            # Fetch full campaign with prospects
            full = self.get_campaign_prospects(cid)
            if not full:
                log("Failed to load campaign", RED)
                continue

            direct_msg = full.get("direct_message", "")
            invite_note = full.get("invite_note", "")
            prospects = [p for p in full.get("prospects", []) if p["status"] == "pending"]

            if not prospects:
                log("No pending prospects", YELLOW)
                continue

            limit = min(len(prospects), BATCH_SIZE, campaign.get("daily_limit", 25))
            log(f"Sending to {limit} prospects...\n", GREEN)

            for i, prospect in enumerate(prospects[:limit]):
                name = prospect.get("name", prospect["public_id"])
                company = prospect.get("company", "")

                log(f"[{i+1}/{limit}] {name} ({company})", BLUE)

                # Mark as sending via CRM API
                # (we'll update after send)

                try:
                    ok, send_type = self.send_to_prospect(headers, prospect, direct_msg, invite_note)
                except Exception as e:
                    ok, send_type = False, str(e)[:80]

                if ok:
                    log(f"  ✓ {send_type}", GREEN)
                    total_sent += 1
                    # Update CRM — mark as sent
                    self.session.post(
                        f"{CRM_URL}/api/crm/campaigns/{cid}/prospect-status",
                        json={"public_id": prospect["public_id"], "status": "sent", "send_type": send_type},
                        timeout=10,
                    )
                else:
                    log(f"  ✗ {send_type}", RED)
                    total_failed += 1
                    self.session.post(
                        f"{CRM_URL}/api/crm/campaigns/{cid}/prospect-status",
                        json={"public_id": prospect["public_id"], "status": "failed", "error": send_type},
                        timeout=10,
                    )

                    # Stop on auth errors
                    if "401" in str(send_type) or "cookie" in str(send_type).lower():
                        log("Cookie rejected — stopping. Get a fresh cookie and try again.", RED)
                        break

                # Human-like delay
                if i < limit - 1:
                    delay = random.randint(DELAY_MIN, DELAY_MAX)
                    log(f"  Waiting {delay}s...", YELLOW)
                    time.sleep(delay)

        print(f"\n{BOLD}{'='*40}")
        print(f"  Done! Sent: {GREEN}{total_sent}{RESET}{BOLD}, Failed: {RED}{total_failed}{RESET}")
        print(f"{'='*40}{RESET}\n")


if __name__ == "__main__":
    sender = LinkedInSender()
    sender.run()
