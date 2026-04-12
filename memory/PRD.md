# PRD — Multi-Agent Platform (Vineet Narang)

## Original Problem Statement
Build a multi-agent platform serving 6 completely independent agents, each accessible via isolated URLs from a unified landing page hub. The agents handle: invoicing, refund generation, stock market scanning, LinkedIn content generation, PDF directory extraction, and account checking.

## Architecture
- **Frontend**: React (React Router v7), Shadcn-inspired dark theme
- **Backend**: FastAPI (Python), MongoDB
- **Routing**: Each agent has its own URL route (`/invoicing`, `/refund`, `/stocks`, `/linkedin`, `/directory`, `/checker`)
- **Auth**: Shared password-based agent login wrapper (`AgentLogin.jsx`), JWT for invoice agent
- **LLM**: Emergent LLM Key via `emergentintegrations` library
- **Image Generation**: Nano Banana (`gemini-3.1-flash-image-preview`) for infographics

## What's Been Implemented

### Agent 1: Invoicing Agent (`/invoicing`)
- PDF upload, first-page extraction, download original/edited, bulk ZIP download
- Date filters (today, week, month, all)

### Agent 2: Refund Agent (`/refund`)
- LLM-powered Google Play refund request generator (GPT-4o)
- History tracking

### Agent 3: Stock Investor (`/stocks`)
- NSE stock scanner (under ₹100, sorted by volume)
- Stock details with price history, news, 52-week analysis
- Portfolio tracker with buy/sell/alerts

### Agent 4: LinkedIn Agent (`/linkedin`)
- LinkedIn OAuth 2.0 integration (connect/disconnect accounts)
- AI content generation for 3 companies (Fundle, HearClear, Tagnpay)
- Post to LinkedIn via API
- Post history
- Auto-post scheduling
- **HearClear Corporate One-Pager**: Unified Blue & Gold McKinsey-standard infographic generated via Nano Banana (`gemini-3.1-flash-image-preview`), with download and regenerate options. Accessible via "HearClear" tab.

### Agent 5: PDF Directory Extractor (`/directory`)
- Upload PDF, background job extracts structured data via pdfplumber
- Excel download of extracted data

### Agent 6: Account Checker (`/checker`)
- DoubleDownCasino account checker with concurrent login via APIs
- Background job polling with results table

### Platform
- Unified landing page hub at `/`
- Agent separation enforced (no shared sidebars)
- No "Emergent" branding visible (CSS override)
- Dark theme with CSS variables

## Prioritized Backlog

### P0
- LinkUp API integration for LinkedIn messaging & auto-commenting

### P1
- SMS/WhatsApp alerts for Stock Investor Agent

### P2
- Fundle.ai specific LinkedIn posts & infographics

### Future
- Continuous monitoring of LinkedIn posts/keywords/people
