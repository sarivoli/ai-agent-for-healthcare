# ARCHITECTURE.md - Living Architectural Blueprint & ADR Log

This document captures the overall system architecture, network/data flows, security boundaries, and any architectural decision records (ADRs) as setup or technologies evolve.

---

## 1. High-Level System Architecture

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │                     CLIENT LAYER (Vendor Application)                  │
 │  [ Embedded Chat Window ]   [ Dynamic UI / Configurable Summarizer ]   │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ User Prompt Request
 ┌───────────────────────────────────▼────────────────────────────────────┐
 │                     1. INPUT GUARDRAIL LAYER                           │
 │  [ Prompt Injection Scan ] [ Scope Check ] [ PHI Masking ] [ Safety ] │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ Sanitized Prompt
 ┌───────────────────────────────────▼────────────────────────────────────┐
 │                ORCHESTRATION & MULTI-AGENT LAYER (LangGraph)           │
 │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
 │  │ Data Ingestion   │  │ Clinical Analyst │  │ Summarization Agent  │  │
 │  │ Agent            │  │ Agent            │  │ (Config. Templates)  │  │
 │  └────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘  │
 └───────────┼─────────────────────┼───────────────────────┼──────────────┘
             │ 2. ACTION VALIDATION (Schema Check + RBAC Permissions)
 ┌───────────▼─────────────────────▼───────────────────────▼──────────────┐
 │                   SECURE MCP HEALTHCARE MIDDLEWARE                     │
 │  [ RBAC Scope Filter & Field-Level Access Control Engine ]             │
 │  [ FHIR Normalization & Schema Translation Layer ]                     │
 └───────────┬─────────────────────┬───────────────────────┬──────────────┘
             │                     │                       │
             ▼                     ▼                       ▼
 ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
 │ Vendor FHIR APIs     │ │ Custom SQL / REST    │ │ Dual-LLM Routing     │
 │ (Labs, Meds, Notes)  │ │ (Schedules, Care)    │ │ Local (PHI) / Cloud  │
 └──────────────────────┘ └──────────────────────┘ └───────────┬──────────┘
                                                               │ Raw LLM Response
 ┌─────────────────────────────────────────────────────────────▼──────────┐
 │                     3. OUTPUT GUARDRAIL LAYER                          │
 │  [ Hallucination Check ] [ Sensitive Leakage Mask ] [ Content Safety ]│
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ Validated Safe Output
                                     ▼ User Response
```

---

## 2. Security & Guardrail Subsystems

### 2.1 Input Guardrails (`src/security/input_guardrails.py`)
- **Sensitive Data Masking:** Automated PHI/PII redactor masking SSNs, MRNs, phone numbers, and full names before prompt submission.
- **Prompt Injection Defense:** Heuristic & regex scanner detecting jailbreaks, system overrides, and prompt manipulation attempts.
- **Scope Validation:** Healthcare domain classifier verifying that prompts remain strictly within clinical boundaries.
- **Content Safety Filter:** Filters out abusive, toxic, or unsafe content.

### 2.2 Action Validations (`src/security/action_validator.py`)
- **Schema & Parameter Validation:** Validates tool call parameters against strict Pydantic/JSON schemas before execution.
- **Permission Enforcement:** Checks caller scopes and RBAC roles before invoking database queries or MCP tools.

### 2.3 Output Guardrails (`src/security/output_guardrails.py`)
- **Hallucination Verification:** Cross-references generated clinical assertions against ground-truth FHIR data resources.
- **Sensitive Leakage Protection:** Redacts unauthorized PHI fields from final user outputs.
- **Content Safety:** Ensures responses comply with safety guidelines and clinical disclaimers.

---

## 3. Architectural Decision Records (ADRs)

| ADR ID | Date | Title | Status | Summary / Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **ADR-001** | 2026-09-20 | FastMCP for MCP Server Implementation | Accepted | FastMCP Python SDK chosen for rapid development and clean decorator-based tool registrations. |
| **ADR-002** | 2026-09-20 | Pydantic v2 FHIR Data Models | Accepted | Use Pydantic v2 for strict type checking and fast JSON normalization of FHIR R4 resources. |
| **ADR-003** | 2026-09-20 | Dual Local/Cloud LLM Privacy Proxy | Accepted | Enforces HIPAA Zero Data Retention (ZDR) by keeping sensitive PHI on local/private inference nodes. |
| **ADR-004** | 2026-09-20 | Comprehensive Input/Action/Output Guardrail Engine | Accepted | Implement dedicated tri-fold security middleware protecting pre-LLM inputs, tool execution actions, and post-LLM outputs. |
| **ADR-005** | 2026-09-23 | Dual-LLM Routing & Automated De-identification Proxy | Accepted | Implement real-time PHI classifier scanning 18 HIPAA categories to route sensitive payloads to local ZDR host nodes (Ollama Llama-3) and de-identified workloads to Cloud LLMs (Gemini 3.6 Flash). |
| **ADR-006** | 2026-10-11 | System-Wide Error Handling, Audit Incident Logging & Output Normalization | Accepted | Implemented centralized text extraction (`src/utils/text_extractor.py`) to seamlessly unpack chunked list payloads and strip cryptographic envelopes, centralized audit incident tracking (`audit_tracker.log_event`) with unique reference IDs (`INC-xxxx`), and empathetic UI notifications with 1-click draft prompt restoration. |
| **ADR-007** | 2026-10-22 | Dedicated Transaction Journey Audit Logging & Dynamic Multi-CRUD Conversational Operations | Accepted | Implemented dedicated `TransactionJourney` auditing in `src/security/audit_tracker.py` recording end-to-end lifecycle traces (JSON artifacts and append-only `audit_journey.log`). Added dynamic chat-driven parsing and database committal for medication orders, lab results (`add_lab_result`), and progress notes (`update_patient_note`) with mandatory HITL clinician attestation gates. Integrated live Google Gemini 3.6 Flash with automated Zero Data Retention (ZDR) PHI de-identification/re-identification proxy. |
| **ADR-008** | 2026-10-22 | Interactive Visual Transaction Audit & Pipeline Journey Explorer (`/audit`) | Accepted | Implemented dedicated browser-based visual audit debugger and compliance ledger (`/audit`, `audit.html`, `audit.js`, `style.css`). Features include real-time polling ledger, subway-style pipeline stepper, plain-language clinical story cards translating machine telemetry, structured CRUD diff parameters, raw telemetry inspection, and an alternate terminal-style immutable journal viewer for `audit_journey.log`. |


