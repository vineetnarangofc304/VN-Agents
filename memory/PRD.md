# PRD — Agent Builder Platform

## Original Problem Statement
Build a platform containing multiple specialized personal assistant agents:
1. **Invoicing Agent**: Download Google Play receipts, remove 2nd page, change page numbering, ZIP download.
2. **Refund Request Agent**: Generate human-sounding refund requests for failed Google Play transactions.
3. **Stock Market Investor**: Scan NSE stocks, filter top 50 by volume under INR 100, highlight undervalued.
4. **LinkedIn Agent**: Manage content, infographics, scheduling, and messaging for personal profile and 3 company pages.

## User Personas
- **Vineet Narang** — Runs 3 companies: HearClear India (Audiology/Healthcare), Fundle.ai (Retail Data Intelligence for Malls), Tagnpay.ai (B2B Channel Loyalty for Manufacturers). Posts LinkedIn content from his profile.
- **Abhinav Khanna** — Posts Fundle.ai content from his LinkedIn profile.

## Core Architecture
- **Frontend**: React.js (single-page app with sidebar nav)
- **Backend**: FastAPI with modular routes
- **Database**: MongoDB (Motor async driver)
- **LLM**: Emergent LLM (OpenAI GPT-4o via emergentintegrations)
- **External**: yfinance (stocks), LinkedIn OAuth 2.0

## What's Been Implemented

### Agent 1: Invoicing Agent [COMPLETE]
- PDF upload, PyPDF2 page extraction, date-based filtering, ZIP download
- Endpoints: POST /api/invoices/upload, GET /api/invoices, GET /api/invoices/download-all

### Agent 2: Refund Request Agent [COMPLETE]
- Emergent LLM generates detailed refund text from transaction details
- Endpoints: POST /api/refund/generate, GET /api/refund/history

### Agent 3: Stock Market Investor [COMPLETE]
- yfinance integration, NSE stocks under INR 100, top 50 by volume, undervalued highlights
- Portfolio tracking with buy/sell alerts
- Endpoints: GET /api/stocks/scanner, GET /api/stocks/{symbol}/details, POST /api/stocks/portfolio/add

### Agent 4: LinkedIn Agent [IN PROGRESS]
- **Completed (April 8, 2026)**:
  - LinkedIn OAuth 2.0 flow (auth URL generation, callback handling, token storage in MongoDB)
  - Multi-account support (connect multiple LinkedIn profiles)
  - Content generation for 3 companies (Fundle.ai, HearClear India, Tagnpay.ai) using Emergent LLM
  - Post composer UI (generate, edit, publish)
  - Post history tracking
  - Auto-post scheduling config (enable/disable, interval selection)
  - Settings page (account management, schedule config)
  - Token refresh handling
  - Error logging for permissions, token expiry, invalid URNs
  
- **Pending**:
  - LinkedIn OAuth redirect URI needs to be added in LinkedIn Developer Portal
  - Actual scheduled posting background task (APScheduler integration)
  - Image/Document post support (2-step upload to LinkedIn)
  - LinkUp API integration for messaging connections and auto-commenting
  - Dynamic Gemini image generation for infographics

## Prioritized Backlog

### P0 (Next)
- User must test LinkedIn OAuth connection flow (add redirect URI to LinkedIn app)
- Implement background scheduler for auto-posting (APScheduler)

### P1
- LinkUp API integration (messaging, auto-commenting)
- Dynamic infographic generation (Gemini Nano Banana)
- Image/Document posting to LinkedIn

### P2
- SMS/WhatsApp alerts for Stock Investor Agent
- LinkedIn organization/company page posting (currently personal profile only)
- LinkedIn post analytics and monitoring

## Key Files
- `/app/backend/server.py` — Main FastAPI app, auth, invoices, refunds, stocks
- `/app/backend/routes/linkedin.py` — LinkedIn OAuth, posting, content generation
- `/app/frontend/src/App.js` — Main React app, all agent views
- `/app/frontend/src/components/LinkedInAgent.jsx` — LinkedIn Agent UI component
- `/app/frontend/src/App.css` — All styling

## Known Issues
- "Noidq" typo in processed invoices (source PDF issue, needs OCR to fix)
- LinkedIn infographics currently static sample files
- OAuth states stored in-memory (lost on restart) — acceptable for current usage
