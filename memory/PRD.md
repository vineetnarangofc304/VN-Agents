# PRD — Multi-Agent Platform (Vineet Narang)

## Original Problem Statement
Build a multi-agent platform serving 9 completely independent agents, each accessible via isolated URLs from a unified landing page hub.

## Architecture
- **Frontend**: React (React Router v7), dark theme (default) + light theme (Content Studio)
- **Backend**: FastAPI (Python), MongoDB
- **Routing**: Each agent on its own URL
- **Auth**: Shared password-based agent login wrapper
- **LLM**: Emergent LLM Key via `emergentintegrations` (GPT-4o for text, Nano Banana for images)

## What's Been Implemented

### Agent 1: Invoicing (`/invoicing`) — PDF upload/first-page extraction/bulk ZIP
### Agent 2: Refund (`/refund`) — LLM-powered Google Play refund generator
### Agent 3: Stock Investor (`/stocks`) — NSE scanner, portfolio tracker
### Agent 4: LinkedIn (`/linkedin`) — OAuth, AI content gen, post to LinkedIn, scheduling, 6hr auto-poster
### Agent 5: PDF Extractor (`/directory`) — PDF to Excel extraction
### Agent 6: Account Checker (`/checker`) — DDC email scanner, credits capture, chip farming
### Agent 7: Catchment Mining (`/catchment`) — Web crawler for Delhi NCR contact databases

### Agent 8: LinkedIn Lead Finder (`/linkedin-search`) — NEW (Jul 2026)
- Post Search via LinkedIn Voyager API (cookie-based auth)
- 10 search keywords, AI classification (GPT-4o), company matching
- AI comment generation & posting
- Messaging tab: fetch connections, AI message generation, single/bulk send

### Agent 9: Content Studio (`/content-studio`) — NEW (Jul 2026)
- **Dashboard**: Stats (total, published, drafts, scheduled), 18 content pillars, recent content
- **AI Content Generation**: 3-step pipeline (Research → Draft → Review/Polish) with quality scoring
- **Content Calendar**: AI-generated publishing schedule (7-90 days)
- **Infographic Generation**: Nano Banana (McKinsey/Stripe quality specs)
- **LinkedIn Publishing**: Separate OAuth for Vineet Narang
- **Content Library**: All generated content with pillar/status/score filters
- **Light Theme UI**: Apple/Stripe quality, Manrope + Inter typography

### Agent 10: Banking Agent (`/banking`) — NEW (Jul 2026)
- **PDF Upload**: Password-protected bank statement parsing (pdfplumber)
- **Auto-Categorization**: 20+ merchant/category mappings (Gaming, Food, Transport, Bills, etc.)
- **Dashboard**: Summary cards (Opening/Closing Balance, Debits, Credits, Net Flow)
- **Overview Tab**: Monthly debits vs credits bar chart, category pie chart, transaction type breakdown
- **Categories Tab**: Horizontal bar chart + clickable table
- **Merchants Tab**: Top 15 merchant chart + full merchant table
- **Trends Tab**: Daily balance area chart, monthly net cash flow
- **Transactions View**: Searchable, sortable, filterable table (2877 txns), pagination (100/page)
- **Filters**: Category, txn type, date range, debit/credit only, text search

## Background Schedulers
- DDC Farm: Daily at 3 PM IST
- Credits Scanner: Daily at 6 AM IST
- LinkedIn Auto-poster: Every 6 hours
- Scheduled Posts: Every 5 minutes check

## Prioritized Backlog

### P0 (Needs User Action)
- **Verify Bulk Messaging Script** — Updated sync script (v8) and messaging script (v3) to use stable profile lookup APIs instead of broken typeahead/blended search. User needs to re-sync connections and test bulk send from LinkedIn browser console. (Jul 2026)
- Connect Vineet's LinkedIn via Content Studio OAuth
- Verify production deployment

### P1 (Content Studio Phase 2)
- Research Agent: Daily monitoring of OpenAI, Anthropic, arXiv, HN
- Idea Inbox: AI-curated content ideas from trending topics
- Analytics & Learning: Track engagement, learn what works
- Brand voice memory & style learning

### P2
- Multiple content types: carousels, whitepapers, architecture diagrams, video scripts
- Asset Library & Version History
- DDC farming gain verification
- Catchment Mining search improvements

### Future
- SMS/WhatsApp alerts for Stock Investor
- Catchment Mining for more cities
- DDC advanced farming
- 365-day full calendar generation
- Conference talk & keynote generators
