# Feature Specification: Visual Transaction Journey & Audit Pipeline Explorer

## 1. Executive Summary

In healthcare AI architectures, opacity is the primary barrier to clinical adoption and regulatory compliance (HIPAA, FDA Software as a Medical Device - SaMD, and EU AI Act). When a clinician or healthcare administrator issues an instruction, they must not treat the agent as a "black box." Every decision, security scan, model routing boundary, and database alteration must be traceable, auditable, and human-understandable.

The **Visual Transaction Journey & Audit Pipeline Explorer** (`/audit`) provides an interactive, stage-by-stage visual debugger and regulatory compliance ledger for the Enterprise Healthcare MCP Platform. It translates deep machine telemetry, LangGraph state transitions, Dual-LLM routing, and EHR database committals into plain-language story cards and interactive visual pipeline maps.

---

## 2. Architectural Overview

```
                                  TRANSACTION LIFECYCLE PIPELINE
                                  
 [Client Chat] ──────> [1. INGRESS_CLIENT]
                               │  (OAuth 2.1 & Role Auth)
                               ▼
                       [2. INPUT_GUARDRAILS]
                               │  (Zero-Token Perimeter Threat Check)
                               ▼
                       [3. CLINICAL_RULES_ENGINE]
                               │  (Deterministic HEDIS Care Gap Check)
                               ▼
                       [4. PHI_SCAN_AND_DEID]
                               │  (Zero-Token De-identification Router)
                               ├── Raw PHI ────────> [5a. LOCAL_LLM_INFERENCE] (Ollama)
                               └── Masked Prompts ──> [5b. CLOUD_LLM_INFERENCE] (Gemini ZDR)
                               ▼
                       [6. HITL_GATE (Interrupt)] ───► Clinician Review
                               │
                       [7. CLINICIAN_ATTESTATION] ───► Approve / Reject
                               │
                       [8. EHR_DB_COMMITTAL] ────────► Mock Healthcare DB (RX/LAB/NOTE)
                               │
                       [9. EGRESS_CLIENT] ───────────► Client UI Render
                               │
                               ▼
             ┌────────────────────────────────────────┐
             │       AuditTracker Subsystem           │
             │  • reports/transaction_traces/*.json   │
             │  • reports/transaction_traces/         │
             │    audit_journey.log                   │
             └────────────────────────────────────────┘
```

---

## 3. Core UI & Functional Capabilities

### 3.1. Top KPI Metrics Ribbon
- **Recorded Transactions**: Real-time count of all transactions logged to disk.
- **HITL Attestations Paused**: Count of operations held at human-in-the-loop review gates.
- **EHR Actions Committed**: Count of clinical mutations written to the patient record.
- **Zero Data Retention Compliance**: 100% verification badge for zero external PHI leakage.

### 3.2. Transaction Ledger & Fast Filter Bar
- **Real-time Live Sync**: Configurable auto-polling (every 4 seconds) preserving active selection and scroll positions.
- **Keyword Search**: Instant multi-attribute search across Trace IDs (`TRX-...`), prompts, Patient IDs (`P101`), and roles.
- **Status Filter Pills**: Quick segmentation by transaction state:
  - `ALL`: Complete history.
  - `AWAITING_APPROVAL`: Transactions paused at attestation gates.
  - `COMPLETED`: Read-only queries or safely finished workflows.
  - `COMMITTED`: Approved and written EHR database actions.
  - `BLOCKED`: Blocked security attacks or rejected orders.

### 3.3. Subway-Style Visual Traversal Pipeline
- Horizontal milestone graph displaying numbered stage nodes.
- Color-coded state indicators:
  - 🟢 **Green (Completed)**: Stage executed successfully.
  - 🟡 **Amber (Paused)**: Graph paused for clinician attestation.
  - 🔴 **Red (Blocked)**: Security threat intercepted or physician rejection.
- Interactive jumping: Clicking any milestone smoothly scrolls and highlights the detailed stage card below.

### 3.4. Plain-Language "Story Cards"
Each milestone card features a plain-language summary answering: *"What happened at this stage in clinical terms?"*:
- **Client Ingress**: Captures originating endpoint, user role, and originating prompt.
- **Zero-Token Guardrails**: Quantifies threat scanning across injection vectors.
- **PHI Classifier**: Reports exact sensitivity score, detected entity classes, and Safe Harbor de-identification.
- **HITL Gate**: Explains the exact write operation proposed (e.g., *"Order medication Lisinopril 20mg daily"*).
- **Clinician Attestation**: Shows physician identity, decision timestamp, and clinical rationale.
- **EHR DB Committal**: Details unique entity IDs (`RX-NEW-...`, `LAB-NEW-...`, `NOTE-NEW-...`) created.

### 3.5. Dual View: Visual Stages vs. Terminal Journal Viewer
- **Visual Stages View**: Split-pane interface with subway flow and expandable cards.
- **Audit Journal Log View**: Terminal-style viewer displaying the immutable, append-only `audit_journey.log` stored on disk. Includes 1-click reload and download capabilities.

### 3.6. LLM Connection & Token Telemetry Ribbon
Integrated directly into the Journey Overview card header, providing real-time infrastructure and financial governance transparency:
- 🌐 **Model & Connection Badge**: Distinguishes between `Cloud LLM (Google Gemini API via langchain-google-genai)` vs. `Local On-Premise LLM (Ollama / vLLM)` with exact endpoint URI.
- ⚡ **Call Tokens Metric**: Shows exact prompt tokens, completion/synthesis tokens, and total tokens consumed by this specific transaction.
- 📊 **Session Quota Tracker**: Displays accumulated token expenditure so far across the current session and remaining quota buffer before rate limits or grace multiplier thresholds apply.

### 3.7. Dynamic Vital Sign (BP) & State Persistence
- **Zero-Hallucination Guard**: Natural conversational BP instructions (e.g., *"add current bp as 140/90"*, *"record blood pressure 130/80"*) are intercepted by dedicated vital-sign regex before generic conversational fallback can hallucinate committal.
- **Human-in-the-Loop Attestation**: Blood pressure records are staged as clinical observations with LOINC `85354-9` (Blood Pressure panel), `8480-6` (Systolic), and `8462-4` (Diastolic).
- **Transactional Persistence**: Upon clinician approval, values are permanently committed to `MockHealthcareDB`.
- **Immediate State Reflection**: Subsequent clinical summaries immediately pull fresh database observations, safely normalizing slash-formatted strings (`"140/90"`) without numerical parsing errors in HEDIS CBP rule calculations.

---

## 4. API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/audit` | Serves the interactive HTML5/CSS3/Vanilla JS visual audit log page. |
| `GET` | `/api/audit/traces` | Returns JSON array of all transaction journey traces sorted chronologically (newest first). |
| `GET` | `/api/audit/traces/{trace_id}` | Returns single transaction journey detail JSON for deep inspection. |
| `GET` | `/api/audit/journey-log` | Returns the raw, append-only plain-text audit journal file content. |

---

## 5. Verification & Test Coverage

Full automated test suite verifying dynamic chat CRUD, BP vital persistence, and transaction trace logging:
```bash
PYTHONPATH=. ./venv/bin/pytest tests/test_dynamic_chat_crud_and_traces.py -v
```

All 74 repository unit, integration, and security tests pass with 100% compliance.

