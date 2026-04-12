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
- **HearClear tab**: 8 themed infographic generator (Market Disruptor, Dementia Connection, AI Revolution, Ecosystem Flywheel, Investor Thesis, Patient Experience, Audiologist Army, India Crisis Map)
- Background generation with polling, persistent storage, download, thumbnails

### Agent 5: PDF Extractor (`/directory`) - PDF to Excel extraction
### Agent 6: Account Checker (`/checker`)
- DDC email scanner with resume, persistent results, Login button per row
- Credits capture planned as Phase 2

### Agent 7: Catchment Mining (`/catchment`) — NEW
- Web crawler for Delhi NCR contact databases
- 15 seed URLs (verified RWA, govt, clubs, professional, senior citizen directories)
- DuckDuckGo search across 656 query combinations
- 8 categories: RWA, Clubs, Schools, Govt, Professional, Religious, Business, Senior Citizens
- Auto-extracts phone numbers, names, emails, addresses from PDFs, Excel, CSV, web pages
- Start/stop/resume with persistent MongoDB storage
- Search, filter by category/city, pagination, Excel export

## Prioritized Backlog

### P0
- LinkUp API for LinkedIn messaging/auto-commenting
- Continue expanding Catchment Mining seed URLs and search queries

### P1
- SMS/WhatsApp alerts for Stock Investor
- DDC credits capture (Phase 2 after full scan)

### P2
- Fundle.ai LinkedIn posts & infographics

### Future
- Continuous LinkedIn monitoring
- Catchment Mining for more cities beyond Delhi NCR
