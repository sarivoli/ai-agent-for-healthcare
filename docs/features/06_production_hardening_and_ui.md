# Module 7 Feature Specification: Production Hardening, RBAC, Session Memory & Web UI

## Overview
Module 7 completes the production hardening of the Enterprise Healthcare MCP Platform. It introduces field-level Role-Based Access Control (RBAC) via simulated OAuth 2.1 tokens, persistent LangGraph state checkpointers, async Human-in-the-Loop (HITL) ticket ETAs, fault-tolerant user input recovery, a FastAPI REST server, an interactive Web Application Dashboard, and Docker deployment.

---

## Architectural Components

### 1. OAuth 2.1 & Field-Level RBAC Middleware (`src/security/rbac.py`)
- **OAuth 2.1 Token Verification:** Decodes bearer tokens (`Bearer clinician_token`, `Bearer analyst_token`, `Bearer auditor_token`) into user identities and role scopes.
- **Action Permission Check:** Enforces scope permissions before executing clinical tools or graph steps.
- **Field-Level Redaction:**
  - `Clinician`: Full unredacted clinical data and write attestation rights.
  - `Analyst`: De-identified clinical notes (author names & note IDs masked as `[REDACTED_FOR_ANALYST]`).
  - `Auditor`: Metadata access with direct patient identities masked as `[REDACTED_BY_AUDITOR_RBAC]`.

### 2. Session Memory Checkpointer & Ticket Manager (`src/agents/session_memory.py`)
- **State Checkpointing:** Binds agent execution snapshots to a `thread_id`.
- **Async Ticket Generator:** When an agent triggers an `interrupt()` pause, the ticket manager generates a ticket object:
  - `ticket_id`: Unique tracking ID (e.g. `HITL-20260923-25467B`).
  - `status`: `AWAITING_CLINICIAN_APPROVAL`.
  - `estimated_eta`: `15 minutes (Clinician Queue)`.
- **Session Survival:** Users can disconnect, close their browser, return with `thread_id`, and query `GET /api/threads/{thread_id}/status` or resume state upon clinician approval.

### 3. Fault-Tolerant Input Persistence (`src/agents/fault_tolerance.py`)
- Saves user input prompts into a draft store before calling agent nodes or tool invocations.
- If an unhandled runtime error occurs, the exception interceptor logs audit events, preserves the prompt input, and returns a fallback recommendation allowing one-click retry.

### 4. FastAPI Server & Interactive Web UI (`src/api/server.py`, `src/ui/`)
- **REST APIs:** `/api/chat`, `/api/threads/{thread_id}/status`, `/api/tickets/pending`, `/api/hitl/approve`, `/api/hitl/reject`.
- **Modern Web Dashboard:** Dark-mode glassmorphic UI featuring live chat streaming, persona switcher, quick prompt chips, and a clinician attestation drawer.

---

## Verification & Execution Instructions

### Running the Milestone Demo Script
```bash
# Windows
.venv\Scripts\python.exe -m scripts.demo_production_ui

# Linux / macOS
python3 -m scripts.demo_production_ui
```

### Running Unit & Integration Tests
```bash
.venv\Scripts\python.exe -m pytest tests/test_production_hardening.py
```

### Running Local Web Application Server
```bash
.venv\Scripts\python.exe -m uvicorn src.api.server:app --port 8000 --reload
# Open http://localhost:8000 in your browser
```

### Running with Docker Container
```bash
docker-compose up --build
```
