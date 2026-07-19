# PRD — Multi-Agent Platform (Vineet Narang)

## Original Problem Statement
Build a multi-agent platform serving 8 completely independent agents, each accessible via isolated URLs from a unified landing page hub.

## Architecture
- **Frontend**: React (React Router v7), dark theme
- **Backend**: FastAPI (Python), MongoDB
- **Routing**: Each agent on its own URL (`/invoicing`, `/refund`, `/stocks`, `/linkedin`, `/linkedin-search`, `/directory`, `/checker`, `/catchment`)
- **Auth**: Shared password-based agent login wrapper
- **LLM**: Emergent LLM Key via `emergentintegrations`
- **Image Generation**: Nano Banana (`gemini-3.1-flash-image-preview`) for infographics

## What's Been Implemented

### Agent 1: Invoicing (`/invoicing`) - PDF upload/first-page extraction/bulk ZIP
### Agent 2: Refund (`/refund`) - LLM-powered Google Play refund generator
### Agent 3: Stock Investor (`/stocks`) - NSE scanner, portfolio tracker
### Agent 4: LinkedIn (`/linkedin`)
- OAuth 2.0, AI content gen, post to LinkedIn, scheduling
- HearClear + Fundle.ai infographics (Nano Banana generation)
- 6-hour background scheduler for auto-posting

### Agent 5: PDF Extractor (`/directory`) - PDF to Excel extraction

### Agent 6: Account Checker (`/checker`)
- DDC email scanner with resume (860 active accounts found from 8,746 emails)
- Credits capture via Playwright `/v2/lobby/game` interception
- Chip Farming (v2): Playwright grid-click strategy for Daily Wheel
- Gain tracking against DB-stored baseline

### Agent 7: Catchment Mining (`/catchment`)
- Web crawler for Delhi NCR contact databases
- 15 seed URLs, 656 query combinations
- Auto-extracts phone, name, email from PDFs/Excel/web pages

### Agent 8: LinkedIn Lead Finder (`/linkedin-search`) — NEW
- **Post Search tab**: Search LinkedIn posts via Voyager API using `li_at` cookie
  - 10 pre-configured search keywords (customizable)
  - Pagination (up to 60 results per keyword)
  - AI classification (GPT-4o): categories (performance marketing, digital marketing, loyalty/rewards, social media, branding, D2C, B2B sales, etc.)
  - Smart company matching (Fundle.ai / TagandPay / Exceed)
  - Relevance scoring (high/medium/low)
  - AI comment generation per post (tailored to matched company)
  - Post commenting via LinkedIn Voyager API
  - Filters by category, company match, relevance
- **Messaging tab**: Send messages to 1st-degree connections
  - Fetch connections list with search & pagination
  - Select individual or bulk connections
  - AI message generation (GPT-4o) with purpose & company context
  - Single and bulk message sending via LinkedIn Voyager API
  - Message log tracking
- **Shared**: Cookie-based LinkedIn session (validates against Voyager /me endpoint)

## Background Schedulers
- DDC Farm: Daily at 3 PM IST
- Credits Scanner: Daily at 6 AM IST
- LinkedIn Auto-poster: Every 6 hours
- Scheduled Posts: Every 5 minutes check

## Prioritized Backlog

### P0 (Needs User Action)
- Provide `li_at` cookie to test LinkedIn search & messaging live
- Verify production deployment (last session's fixes)

### P1
- LinkUp API for LinkedIn messaging/auto-commenting
- DDC farming gain verification (waiting for next cycle)
- SMS/WhatsApp alerts for Stock Investor

### P2
- Catchment Mining search improvements (rate limits)
- Continuous LinkedIn monitoring
- Daily automated LinkedIn search scheduler

### Future
- Catchment Mining for more cities
- DDC advanced farming (bingo, chest opens, coin boost)
