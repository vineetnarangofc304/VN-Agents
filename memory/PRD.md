# PRD — LinkedLeads.ai (Multi-Agent Platform)

## Original Problem Statement
Build a multi-agent platform serving 10 independent agents. Current focus: **LinkedLeads.ai** — a LinkedIn Automation CRM with Chrome Extension for safe, browser-based outreach.

## Architecture
- **Frontend**: React (React Router v7), white + blue professional theme
- **Backend**: FastAPI (Python), MongoDB
- **Auth**: JWT-based CRM authentication (bcrypt + Bearer tokens)
- **LLM**: Emergent LLM Key via emergentintegrations
- **Object Storage**: Emergent Object Storage for persistent file hosting
- **Chrome Extension**: MV3, runs on user's real browser/IP for LinkedIn actions

## LinkedLeads.ai — Current State

### Chrome Extension (NEW - v1.0)
- MV3 Chrome Extension with popup UI (login, dashboard, settings)
- Content script on linkedin.com — executes Voyager API calls from user's real browser/IP
- Background service worker — handles auth, task polling, result reporting
- Features: Auto-connect, auto-message, profile visits, human-like delays, daily limits, working hours
- Downloadable as ZIP from `/api/ext/download`
- Files: `/app/chrome-extension/` (manifest.json, background.js, content.js, popup/)

### CRM Frontend (`/linkedin-crm`)
- **White + Blue Professional UI** — LinkedLeads.ai branding
- Dashboard: Stats cards, quick actions, active campaigns overview
- Campaigns: Create, expand (prospect table), upload XLSX, pause/resume/delete
- Prospects: Cross-campaign view with search and filter
- Extension: Download page with setup steps and feature list
- Settings: Account info, manual LinkedIn cookie input
- Admin: User management (super_admin only)

### Backend API
- `/api/crm-auth/*` — Login, JWT tokens, user CRUD, cookie management
- `/api/ext/*` — Extension API (campaigns, tasks, session, stats, download)
- `/api/crm/*` — Legacy campaign manager (Voyager-based, server-side)

### Campaign System (Extension-powered)
- Create campaigns with type (connect/message/visit) and message templates
- Upload XLSX prospect sheets with auto-column mapping
- Extension polls for pending tasks and executes from user's browser
- Full task lifecycle: pending → in_progress → completed/failed
- Real-time stats tracking (daily connects, messages, visits)
- Pause/resume/delete campaigns

### Key DB Collections (Extension)
- `ext_campaigns` — Campaign definitions
- `ext_tasks` — Individual prospect tasks
- `ext_task_log` — Daily action tracking
- `ext_sessions` — Extension session reporting

### Existing Integrations
- WhatsApp (Qikchat): send/send-bulk, message history
- MCP Server: LinkedIn → ChatGPT (6 read-only tools)
- Object Storage: Emergent Object Storage for file persistence

## CRM Accounts
- vineet@channelloyalty.ai (Super Admin)
- chandra@channelloyalty.ai (User)
- abhinav@channelloyalty.ai (User)
- shivam@channelloyalty.ai (User)
- Password for all: CRM@2026!

## Completed (Aug 31, 2026)
- Built Chrome Extension (MV3) for LinkedIn automation
- Built Extension Backend API (campaigns, tasks, stats, download)
- Redesigned CRM UI to white + blue professional (LinkedLeads.ai branding)
- Full campaign lifecycle: create → upload XLSX → extension executes → results tracked
- Extension download as ZIP from CRM
- Fixed all testing agent issues (update-cookies endpoint, task refresh, ObjectId guard, XLSX error handling, cookie redaction)

## Upcoming Tasks
- P0: LinkedIn Company Page OAuth for automated posting (blocked on valid token)
- P1: AI Agent — Auto-personalize messages using Emergent LLM Key (GPT/Claude)
- P1: Multi-step Sequences (Day 1: Visit → Day 3: Connect → Day 7: Message)
- P1: Unified Inbox (LinkedIn + WhatsApp conversations in one view)
- P2: Chrome Web Store submission preparation
- P2: Project Manager Agent (WhatsApp + Google Docs + Dashboard)
- P3: Chrome Extension Monetization (Freemium + Stripe)
- P3: Email messaging integration (SMTP)
- P4: Apollo.io API for MCP server
