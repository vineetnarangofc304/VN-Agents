# PRD — Agent Hub Platform

## Architecture
- Each agent is **completely independent** — own URL, own login, own DB collections, own code
- Landing page at `/` with 6 agent cards
- Each agent accessible at its own URL: `/invoicing`, `/refund`, `/stocks`, `/linkedin`, `/directory`, `/checker`
- Common password: `Agent@2024!`
- React Router for URL-based routing
- No shared sidebar or dashboard — each agent is standalone

## Tech Stack
- Frontend: React.js + React Router v7
- Backend: FastAPI with modular routes
- Database: MongoDB (Motor async)
- LLM: Emergent LLM (GPT-4o)
- Browser Automation: Playwright
- PDF: pdfplumber, PyPDF2, openpyxl

## Agents

### 1. Invoicing Agent [COMPLETE] — `/invoicing`
- PDF upload, page extraction, date filtering, ZIP download

### 2. Refund Agent [COMPLETE] — `/refund`
- LLM-powered refund request generation

### 3. Stock Investor [COMPLETE] — `/stocks`
- NSE stocks under INR 100, top 50 volume, undervalued highlights, portfolio

### 4. LinkedIn Agent [IN PROGRESS] — `/linkedin`
- OAuth flow built, content generation for 3 companies, post composer
- HearClear strategic posts generated (5 posts)
- Infographics pending (image gen quota exceeded)

### 5. PDF Extractor [COMPLETE] — `/directory`
- 125 companies extracted from G20 DIA Summit PDF, searchable table, Excel download

### 6. Account Checker [COMPLETE] — `/checker`
- DDC bulk login checker, 9 ranges, 24,506 combinations, Playwright automation

## Key Files
- `/app/frontend/src/App.js` — React Router + agent routing
- `/app/frontend/src/components/LandingPage.jsx`
- `/app/frontend/src/components/AgentLogin.jsx`
- `/app/frontend/src/components/InvoicingAgent.jsx`
- `/app/frontend/src/components/RefundAgent.jsx`
- `/app/frontend/src/components/StockAgent.jsx`
- `/app/frontend/src/components/LinkedInAgent.jsx`
- `/app/frontend/src/components/DirectoryAgent.jsx`
- `/app/frontend/src/components/AccountChecker.jsx`
- `/app/backend/server.py`
- `/app/backend/routes/linkedin.py`
- `/app/backend/routes/directory.py`
- `/app/backend/routes/account_checker.py`

## Backlog
### P0
- Generate HearClear infographics (quota resets daily)
- LinkedIn OAuth connection test

### P1
- Fundle.ai and Tagnpay.ai strategic posts
- LinkUp API for messaging/commenting
- Auto-posting scheduler (APScheduler)

### P2
- SMS/WhatsApp stock alerts
- LinkedIn org/company page posting
