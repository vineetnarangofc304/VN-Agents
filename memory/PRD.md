# Personal Assistant Agents Platform - PRD

## Original Problem Statement
Build a platform for personal assistant agents that perform various tasks across multiple platforms and channels. Each agent handles specific tasks, agents are modular and can be modified as needs evolve.

## Architecture
- **Backend**: FastAPI + MongoDB + JWT Auth (httpOnly cookies)
- **Frontend**: React with AuthContext, Tailwind CSS
- **PDF Processing**: PyPDF2 + ReportLab

## User Personas
- **Primary User**: Vineet (Admin) - manages invoices and future agents

## Core Requirements (Static)
1. Agent-based architecture with left sidebar navigation
2. Authentication system (JWT with httpOnly cookies)
3. Modular design - add new agents over time

---

## Agent 1: Invoicing Agent

### Features Implemented (Jan 2026)
- [x] Manual PDF upload (multi-file support)
- [x] PDF Processing: Remove page 2, change "Page 1 of 2" → "Page 1 of 1"
- [x] Store both original and edited versions
- [x] Download individual (original/edited)
- [x] Download all edited as ZIP
- [x] Delete invoices
- [x] Invoice list with status indicators

### Technical Implementation
- Upload endpoint: `POST /api/invoices/upload`
- List endpoint: `GET /api/invoices`
- Download original: `GET /api/invoices/{id}/original`
- Download edited: `GET /api/invoices/{id}/edited`
- Download all: `GET /api/invoices/download-all`
- Delete: `DELETE /api/invoices/{id}`

---

## What's Been Implemented
| Date | Feature | Status |
|------|---------|--------|
| Jan 2026 | Auth System (JWT + httpOnly cookies) | ✅ Complete |
| Jan 2026 | Admin Seeding | ✅ Complete |
| Jan 2026 | Invoicing Agent - Full MVP | ✅ Complete |
| Jan 2026 | Dashboard with Sidebar Navigation | ✅ Complete |

---

## Prioritized Backlog

### P0 (Next)
- User-defined invoice text replacement (customizable "Page X of Y" patterns)

### P1 (High Priority)
- Batch processing progress indicator
- Invoice preview before download

### P2 (Future)
- Agent 2: TBD (based on user needs)
- Agent 3: TBD
- Export to cloud storage (Google Drive integration)

---

## Next Tasks
1. Await user's next agent requirement
2. Consider adding invoice preview feature
3. Add customizable text replacement patterns
