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
- **Object Storage**: Emergent Object Storage for persistent file hosting (campaign PDFs, prospects)

## What's Been Implemented

### Agent 1-7, 9-10: (Unchanged — see previous PRD versions)

### Agent 8: LinkedIn Lead CRM (`/linkedin-search`) — REVAMPED Aug 2026
**Full CRM redesign** from monolithic 1162-line component to modular 8-file architecture:

#### CRM Views
- **Dashboard**: KPI cards (Total Contacts, Messages Sent, Contacted, Response Rate), Recent Messages, Recent Leads
- **Pipeline**: Kanban board with 6 stages (New Lead, Connected, Messaged, Replied, Follow-up, Converted)
- **Search**: Post search with AI classification, keyword management, auto-commenting engine
- **Contacts**: Sortable table with bulk selection, search, pagination, contact detail drawer
- **Messages**: Compose panel with recipient search, AI generation per company, message history
- **WhatsApp**: Qikchat-powered WhatsApp messaging with CRM contact picker, message history, send stats
- **Campaigns**: Bulk outreach campaign manager with 500 Myntra prospects, send tracking, retry mechanism
- **Company Pages**: LinkedIn company page auto-posting (REST API, requires OAuth)
- **Settings**: LinkedIn cookie manager, Chrome extension download

#### CRM Architecture
- Sidebar navigation with view switching (9 views including WhatsApp)
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
- Campaign Auto-sender: Every 30 minutes (5 messages per batch)

## Key DB Collections
- `li_accounts`: `{account_id, name, linkedin_url, created_at, is_default}`
- `li_connections`: `{public_id, full_name, occupation, company, email, phone, account_id, lead_stage, ...}`
- `li_message_log`: `{public_id, recipient_name, message, account_id, sent_at}`
- `li_message_queue`: `{recipients, message, account_id, status, created_at}`
- `outreach_campaigns`: `{campaign_id, name, message_template, attachment_cloud_path, status, daily_limit}`
- `campaign_prospects`: `{campaign_id, public_id, name, brand, status, sent_at, error}`
- `whatsapp_messages`: `{id, phone, contact_name, message, channel, status, sent_at}`

## Recent Changes (Aug 22, 2026)
- **Emergent Object Storage**: Campaign PDF brochure (486KB) and prospects XLSX (106KB) uploaded to persistent cloud storage. Campaign manager falls back to cloud when local files missing.
- **Qikberry WhatsApp Integration**: Full Qikchat API integration with phone validation (E.164), send/send-bulk endpoints, message history, stats. Frontend WhatsApp view with CRM contact picker.
- **Code cleanup**: Removed dead duplicate async upload function, fixed invalid CSS props, added maxLength to textarea, improved send button contrast for accessibility.

## Prioritized Backlog

### P0 (Blocked)
- **LinkedIn Company Page OAuth**: REST API posting requires valid OAuth token with `w_organization_social` scope. Blocked on user providing fresh token.

### P1
- **People Search**: Add Voyager API people search by keywords/title/company/industry
- **Connection Requests**: Send personalized connection requests from CRM

### P2
- Project Manager Agent (WhatsApp + Google Docs + Dashboard)
- Chrome Extension Monetization (Freemium + Stripe)
- Email SMTP Integration (waiting for credentials)

### Future
- Network Analytics Dashboard
- LinkedIn Post Search Scheduler
- Content Studio Phase 2
- Research Agent
- Mobile responsive CRM layout
- Campaign prospects pagination
