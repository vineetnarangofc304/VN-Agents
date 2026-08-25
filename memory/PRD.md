# PRD — Multi-Agent Platform (Vineet Narang)

## Original Problem Statement
Build a multi-agent platform serving 10 independent agents, each accessible via isolated URLs from a unified landing page hub.

## Architecture
- **Frontend**: React (React Router v7), dark theme CRM
- **Backend**: FastAPI (Python), MongoDB
- **Auth**: Password-based agent login (Agent@2024!)
- **LLM**: Emergent LLM Key via emergentintegrations
- **Object Storage**: Emergent Object Storage for persistent file hosting
- **MCP Server**: LinkedIn MCP (felipfr/linkedin-mcpserver fork) exposed via supergateway + FastAPI proxy

## Agent 8: LinkedIn Lead CRM — Current State

### CRM Views (9 total)
- Dashboard, Pipeline, Search, Contacts, Messages, WhatsApp, Campaigns, Company Pages, Settings

### Campaign System
- **Myntra 500**: 91 prospects, Marketplace AutoPilot pitch (Vineet)
- **Trade Marketing 500**: 160 prospects from ChannelLoyalty.ai sheet, connection request + note (Chandra, CBO)
- Smart send: tries direct message first, falls back to connection request with 300-char personalized note
- Auto-sender: 5 messages every 30 minutes, 25/day limit
- Cloud storage: PDF brochure + XLSX persist via Emergent Object Storage

### WhatsApp (Qikchat)
- Full integration: send/send-bulk, message history, CRM contact picker
- API Key: auAF-SnAv-R6VI

### MCP Server (LinkedIn → ChatGPT)
- 6 read-only tools: search-people, get-profile, get-my-profile, get-connections, get-network-stats, search-jobs
- Proper annotations (readOnlyHint, outputSchema)
- send-message disabled for safety
- **BLOCKED**: LinkedIn Voyager API rejects cookies from cloud IPs for search. Profile resolution + messaging work.

### LinkedIn Accounts
- Vineet Narang (default) — Cookie valid, used for campaign sending
- Chandra (CBO) — Added, cookie IP-bound issue
- Abhinav Khanna — OAuth connected, token for REST API

### Key DB Collections
- li_accounts, li_connections, li_message_log, li_message_queue
- outreach_campaigns, campaign_prospects
- whatsapp_messages, li_search_config

## Recent Changes (Aug 25, 2026)
- Fixed Voyager profile resolution (removed stale decorationId)
- Added smart message fallback: direct message → connection request with note
- Trade Marketing 500 campaign: 160 prospects imported, 5 test sends successful
- Fixed banking agent PDF parsing for password-protected files
- LinkedIn MCP server: 6 read-only tools, proper annotations, timeout handling
- Chandra added as LinkedIn account

## Prioritized Backlog

### P0
- Campaign execution: 155 remaining Trade Marketing prospects to send

### P1
- Connection acceptance tracker (who accepted, follow-up queue)
- LinkedIn Company Page OAuth (blocked on valid token with w_organization_social)

### P2
- Project Manager Agent (WhatsApp + Google Docs + Dashboard)
- Chrome Extension Monetization (Freemium + Stripe)
- Email SMTP Integration

### Future
- Apollo.io integration for MCP people search
- Campaign analytics dashboard
- Mobile responsive CRM
