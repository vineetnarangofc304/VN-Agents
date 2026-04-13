# PRD — Multi-Agent Platform (Vineet Narang)

## Original Problem Statement
Build a multi-agent platform serving 7 completely independent agents, each accessible via isolated URLs from a unified landing page hub.

## Architecture
- **Frontend**: React (React Router v7), dark theme
- **Backend**: FastAPI (Python), MongoDB
- **Routing**: Each agent on its own URL (`/invoicing`, `/refund`, `/stocks`, `/linkedin`, `/directory`, `/checker`, `/catchment`)
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
- **Chip Farming (v2)**: Complete rewrite with Bearer token auth approach
  - Promo link scraping from 6 fan sites (344+ links per scan)
  - DWS (Daily Wheel Service) API discovered: `/dws/client/v2/ack/dailyspin/{key}`
  - Bearer JWT token capture and direct Python HTTP API calls
  - Terms popup acceptance handler
  - Coordinate-based UI click for COLLECT and time bonus
  - Gain tracking against DB-stored baseline
  - Proven: daily wheel adds ~100K-500K chips per account per day

### Agent 7: Catchment Mining (`/catchment`)
- Web crawler for Delhi NCR contact databases
- 15 seed URLs, 656 query combinations
- Auto-extracts phone, name, email from PDFs/Excel/web pages

## DDC Chip Farming Architecture (Discovered)
- Auth: Bearer JWT token from `/v2/authenticate/user` response
- Game API base: `https://ap-{shard}.doubledowncasino2.com` (dynamic per user)
- Session ID format: `lg-{uuid}-{shard}-{session_hash}`
- DWS key: extracted from offcanvas iframe URL `a_l_skey` param
- SFS httpbox: commands go to `/httpbox/{commandName}` NOT `/httpbox/poll`
- Daily wheel: auto-spins on login, COLLECT via `/dws/client/v2/ack/dailyspin/{key}`
- Terms popup: blocks game on first login, must be dismissed first

## Prioritized Backlog

### P0 (In Progress)
- Improve DDC daily wheel COLLECT reliability (timing/coordinates)
- DDC promo code claiming via SFS redeemPromo or browser navigation

### P1
- LinkUp API for LinkedIn messaging/auto-commenting
- DDC farming scheduled at 3 PM IST daily
- Deploy for 24/7 operation

### P2
- SMS/WhatsApp alerts for Stock Investor
- Catchment Mining search improvements (rate limits)
- Continuous LinkedIn monitoring

### Future
- Catchment Mining for more cities
- DDC advanced farming (bingo, chest opens, coin boost)
