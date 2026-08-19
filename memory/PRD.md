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

### Agent 1-7, 9-10: (Unchanged — see previous PRD versions)

### Agent 8: LinkedIn Lead CRM (`/linkedin-search`) — REVAMPED Aug 2026
**Full CRM redesign** from monolithic 1162-line component to modular 8-file architecture:

#### CRM Views (New)
- **Dashboard**: KPI cards (Total Contacts, Messages Sent, Contacted, Response Rate), Recent Messages, Recent Leads
- **Pipeline**: Kanban board with 6 stages (New Lead, Connected, Messaged, Replied, Follow-up, Converted)
- **Search**: Post search with AI classification, keyword management, auto-commenting engine
- **Contacts**: Sortable table with bulk selection, search, pagination, contact detail drawer
- **Messages**: Compose panel with recipient search, AI generation per company, message history
- **Settings**: LinkedIn cookie manager, Chrome extension download

#### CRM Architecture
- Sidebar navigation with view switching
- Top header with multi-account switcher (Hardik, Shivam, Vineet)
- Design: Deep Obsidian (#09090b) base, Manrope headings, IBM Plex Sans body, #2563eb primary
- Files in `/app/frontend/src/components/crm/`

#### Existing Features (Carried Over)
- Post Search via LinkedIn Voyager API (cookie-based auth)
- AI classification (GPT-4o), company matching
- AI comment generation & posting
- Multi-User CRM: Account switching, isolated contacts/messages
- Messaging: fetch connections, AI message generation, single/bulk send
- Contact Enrichment: email & phone via Chrome extension

### Chrome Extension: LinkedIn Lead Agent v2.0.0 (Unchanged)

## Background Schedulers
- DDC Farm: Daily at 3 PM IST
- Credits Scanner: Daily at 6 AM IST
- LinkedIn Auto-poster: Every 6 hours
- Scheduled Posts: Every 5 minutes check

## Key DB Collections
- `li_accounts`: `{account_id, name, linkedin_url, created_at, is_default}`
- `li_connections`: `{public_id, full_name, occupation, company, email, phone, account_id, lead_stage, ...}`
- `li_message_log`: `{public_id, recipient_name, message, account_id, sent_at}`
- `li_message_queue`: `{recipients, message, account_id, status, created_at}`

## Recent Fixes (Aug 18-19, 2026)
- Production Backend Crash (HTTP 520) — Fixed startup_event try/except
- CRM Revamp — Full redesign from monolith to modular CRM
- ContactsView sort_dir bug — Fixed string vs int parameter mismatch

## Prioritized Backlog

### P0 (Next — CRM Phase 2)
- **People Search**: Add Voyager API people search by keywords/title/company/industry
- **Connection Requests**: Send personalized connection requests from CRM
- **Follow-up Automation**: Track responses, auto-remind for no-response follow-ups
- **Lead Scoring**: AI-powered 1-10 scoring based on profile + engagement

### P1
- **Qikberry WhatsApp Integration**: Credentials provided (API Key: auAF-SnAv-R6VI)
- **Saved Search Automation**: Daily auto-run of saved searches
- **Campaign Manager**: Drip sequences for outreach

### P2
- Project Manager Agent (WhatsApp + Google Docs + Dashboard)
- Chrome Extension Monetization (Freemium + Stripe)
- Email SMTP Integration (waiting for credentials)

### Future
- Network Analytics Dashboard
- LinkedIn Post Search Scheduler
- Content Studio Phase 2
- Research Agent
