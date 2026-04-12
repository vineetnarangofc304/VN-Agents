# PRD — Agent Builder Platform

## Original Problem Statement
Build a platform with multiple specialized personal assistant agents:
1. **Invoicing Agent**: Download Google Play receipts, remove 2nd page, change page numbering, ZIP download.
2. **Refund Request Agent**: Generate human-sounding refund requests for failed Google Play transactions.
3. **Stock Market Investor**: Scan NSE stocks, filter top 50 by volume under INR 100, highlight undervalued.
4. **LinkedIn Agent**: Manage content, infographics, scheduling, and messaging.
5. **PDF Directory Extractor**: Extract company details from PDF directories into searchable table & Excel.
6. **Account Checker**: Bulk-test DoubleDownCasino email logins, find active accounts.

## Core Architecture
- **Frontend**: React.js (sidebar nav, 6 agent components)
- **Backend**: FastAPI with modular routes (/routes/linkedin.py, /routes/directory.py, /routes/account_checker.py)
- **Database**: MongoDB
- **LLM**: Emergent LLM (GPT-4o)
- **Browser Automation**: Playwright (Account Checker)
- **External**: yfinance (stocks), LinkedIn OAuth 2.0, pdfplumber (PDF extraction)

## What's Been Implemented

### Agent 1: Invoicing Agent [COMPLETE]
### Agent 2: Refund Request Agent [COMPLETE]
### Agent 3: Stock Market Investor [COMPLETE]
### Agent 4: LinkedIn Agent [PARTIAL - OAuth parked]
### Agent 5: PDF Directory Extractor [COMPLETE]
### Agent 6: Account Checker [COMPLETE - April 12, 2026]
- 9 email ranges configured (24,506 total combinations)
- Playwright-based browser automation with 5 concurrent workers
- Background scanning with real-time progress polling
- Active accounts table with live updates
- Excel download of successful logins
- Start/Stop scan controls

## Email Ranges
- veenu001-9999, vinty300-1000, crazy300-1000, strike100-700
- treaty0001-1000, vineet100-10000, vngnara500-1000, vininara300-600, super300-1100
- All @gmail.com, password: c304i109

## Prioritized Backlog
### P0
- LinkedIn OAuth (parked - needs user's LinkedIn app credentials with org permissions)
- APScheduler for auto-posting

### P1
- LinkUp API integration
- Dynamic infographic generation (Gemini)
- Image/Document posting to LinkedIn

### P2
- SMS/WhatsApp alerts for Stock Agent
- LinkedIn organization/company page posting
- Post analytics

## Key Files
- `/app/backend/server.py` — Main app, auth, invoices, refunds, stocks
- `/app/backend/routes/linkedin.py` — LinkedIn OAuth, posting, content gen
- `/app/backend/routes/directory.py` — PDF extraction, companies API, Excel
- `/app/backend/routes/account_checker.py` — DDC login checker
- `/app/frontend/src/App.js` — Main React app
- `/app/frontend/src/components/LinkedInAgent.jsx`
- `/app/frontend/src/components/DirectoryAgent.jsx`
- `/app/frontend/src/components/AccountChecker.jsx`
