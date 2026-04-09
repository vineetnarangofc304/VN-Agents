# PRD — Agent Builder Platform

## Original Problem Statement
Build a platform containing multiple specialized personal assistant agents:
1. **Invoicing Agent**: Download Google Play receipts, remove 2nd page, change page numbering, ZIP download.
2. **Refund Request Agent**: Generate human-sounding refund requests for failed Google Play transactions.
3. **Stock Market Investor**: Scan NSE stocks, filter top 50 by volume under INR 100, highlight undervalued.
4. **LinkedIn Agent**: Manage content, infographics, scheduling, and messaging for personal profile and 3 company pages.
5. **PDF Directory Extractor**: Extract company details from PDF directories into searchable table & Excel.

## User Personas
- **Vineet Narang** — Runs 3 companies: HearClear India (Audiology/Healthcare), Fundle.ai (Retail Data Intelligence for Malls), Tagnpay.ai (B2B Channel Loyalty for Manufacturers). Posts LinkedIn content from his profile.
- **Abhinav Khanna** — Posts Fundle.ai content from his LinkedIn profile.

## Core Architecture
- **Frontend**: React.js (single-page app with sidebar nav)
- **Backend**: FastAPI with modular routes (/routes/linkedin.py, /routes/directory.py)
- **Database**: MongoDB (Motor async driver)
- **LLM**: Emergent LLM (OpenAI GPT-4o via emergentintegrations)
- **External**: yfinance (stocks), LinkedIn OAuth 2.0, pdfplumber (PDF extraction)

## What's Been Implemented

### Agent 1: Invoicing Agent [COMPLETE]
- PDF upload, PyPDF2 page extraction, date-based filtering, ZIP download

### Agent 2: Refund Request Agent [COMPLETE]
- Emergent LLM generates detailed refund text from transaction details

### Agent 3: Stock Market Investor [COMPLETE]
- yfinance integration, NSE stocks under INR 100, top 50 by volume, undervalued highlights

### Agent 4: LinkedIn Agent [PARTIALLY COMPLETE]
- LinkedIn OAuth 2.0 flow (auth URL, callback, token storage, refresh)
- Multi-account support
- Content generation for 3 companies (Fundle.ai, HearClear India, Tagnpay.ai) via LLM
- Post composer UI (generate, edit, publish)
- Post history, scheduling config, settings page
- **Pending**: User must add redirect URI to LinkedIn Dev Portal, actual scheduled posting

### Agent 5: PDF Directory Extractor [COMPLETE - April 9, 2026]
- Extracts company data from PDF directories (tested with G20 DIA Summit PDF)
- pdfplumber-based extraction with regex field parsing
- Background thread processing for large PDFs (avoids proxy timeout)
- 125 companies extracted with: Name, Address, Contact Person, Designation, Phone, Mobile, Email, Website, Profile
- Searchable/filterable table UI with expandable row details
- Excel download with professional formatting (headers, borders, auto-filter, freeze panes)
- MongoDB storage in 'exhibitors' collection

## Prioritized Backlog

### P0 (Next)
- LinkedIn OAuth testing (user needs to add redirect URI to LinkedIn Dev Portal)
- Implement APScheduler background task for auto-posting every 4 hours

### P1
- LinkUp API integration for messaging connections & auto-commenting
- Dynamic infographic generation (Gemini Nano Banana)
- Image/Document posting to LinkedIn

### P2
- SMS/WhatsApp alerts for Stock Investor Agent
- LinkedIn organization/company page posting
- LinkedIn post analytics

## Key Files
- `/app/backend/server.py` — Main FastAPI app, auth, invoices, refunds, stocks
- `/app/backend/routes/linkedin.py` — LinkedIn OAuth, posting, content generation
- `/app/backend/routes/directory.py` — PDF extraction, companies API, Excel download
- `/app/frontend/src/App.js` — Main React app, all agent views
- `/app/frontend/src/components/LinkedInAgent.jsx` — LinkedIn Agent UI
- `/app/frontend/src/components/DirectoryAgent.jsx` — PDF Extractor UI
- `/app/frontend/src/App.css` — All styling

## Known Issues
- "Noidq" typo in processed invoices (source PDF issue, needs OCR)
- LinkedIn infographics currently static sample files
- OAuth states and extraction jobs stored in-memory (lost on restart)
