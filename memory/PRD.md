# PRD — Multi-Agent Platform (Vineet Narang)

## Original Problem Statement
Build a multi-agent platform serving 10 completely independent agents, each accessible via isolated URLs from a unified landing page hub.

## Architecture
- **Frontend**: React (React Router v7), dark theme (default) + light theme (Content Studio)
- **Backend**: FastAPI (Python), MongoDB
- **Routing**: Each agent on its own URL
- **Auth**: Shared password-based agent login wrapper (Password: Agent@2024!)
- **LLM**: Emergent LLM Key via `emergentintegrations` (GPT-4o for text, Nano Banana for images)
- **Chrome Extension**: LinkedIn Lead Agent v2.0.0 (Multi-Account)

## What's Been Implemented

### Agent 1: Invoicing (`/invoicing`) — PDF upload/first-page extraction/bulk ZIP
### Agent 2: Refund (`/refund`) — LLM-powered Google Play refund generator
### Agent 3: Stock Investor (`/stocks`) — NSE scanner, portfolio tracker
### Agent 4: LinkedIn (`/linkedin`) — OAuth, AI content gen, post to LinkedIn, scheduling, 6hr auto-poster
### Agent 5: PDF Extractor (`/directory`) — PDF to Excel extraction
### Agent 6: Account Checker (`/checker`) — DDC email scanner, credits capture, chip farming
### Agent 7: Catchment Mining (`/catchment`) — Web crawler for Delhi NCR contact databases

### Agent 8: LinkedIn Lead Finder (`/linkedin-search`) — UPDATED Aug 2026
- Post Search via LinkedIn Voyager API (cookie-based auth)
- 10 search keywords, AI classification (GPT-4o), company matching
- AI comment generation & posting
- **Multi-User CRM** (NEW): Account dropdown to switch between LinkedIn profiles
  - Add/remove people (e.g., Hardik Sachdeva, Shivam Narang)
  - Each account has isolated contacts, messages, stats
  - Backend: `li_accounts` collection, all endpoints filter by `account_id`
- Messaging tab: fetch connections, AI message generation, single/bulk send
- Contact Enrichment: Fetch email & phone via LinkedIn Dash API (extension)

### Agent 9: Content Studio (`/content-studio`)
- **Dashboard**: Stats, content pillars, recent content
- **AI Content Generation**: 3-step pipeline with quality scoring
- **Content Calendar**: AI-generated publishing schedule
- **Infographic Generation**: Nano Banana
- **LinkedIn Publishing**: Separate OAuth for Vineet Narang
- **Light Theme UI**: Apple/Stripe quality

### Agent 10: Banking Agent (`/banking`)
- PDF Upload, Auto-Categorization, Dashboard, Charts, Transactions

### Chrome Extension: LinkedIn Lead Agent v2.0.0 (Aug 2026)
- **Multi-Account Support**: Account selector in popup + content script
- **Manifest V3** Chrome extension for LinkedIn automation
- **Floating Panel**: ⚡ button on LinkedIn pages with Sync + Message Queue
- **Auto-Sync**: Syncs connections directly to backend with `account_id`
- **Enrichment**: Fetch email/phone scoped to active account
- **Message Queue**: Pick up message queues per account
- Download: `/linkedin-lead-agent-extension.zip`

## Background Schedulers
- DDC Farm: Daily at 3 PM IST
- Credits Scanner: Daily at 6 AM IST
- LinkedIn Auto-poster: Every 6 hours
- Scheduled Posts: Every 5 minutes check

## Key DB Collections
- `li_accounts`: `{account_id, name, linkedin_url, created_at, is_default}`
- `li_connections`: `{public_id, full_name, occupation, company, email, phone, account_id, ...}`
- `li_message_log`: `{public_id, recipient_name, message, account_id, sent_at}`
- `li_message_queue`: `{recipients, message, account_id, status, created_at}`

## Prioritized Backlog

### P0 (Next)
- **Qikberry WhatsApp Integration**: Credentials provided (API Key: auAF-SnAv-R6VI). Add WhatsApp send button per contact in CRM.
- **Email SMTP Integration**: Blocked — waiting on user for SMTP credentials.

### P1
- LinkedIn Post Search Scheduler (automated daily runs)
- Research Agent: Daily monitoring of OpenAI, Anthropic, arXiv, HN
- Content Studio Phase 2 (Idea Inbox, Analytics)

### P2
- Catchment Mining proxy-based scraping
- Multiple content types: carousels, whitepapers
- DDC farming gain verification

### Future
- SMS/WhatsApp alerts for Stock Investor
- Catchment Mining for more cities
- 365-day full calendar generation
