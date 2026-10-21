# Feature Documentation: System Error Handling, Audit Incident Logging & Output Normalization

## Feature Overview
In clinical AI systems, unhandled runtime crashes, confusing stack traces, or raw JSON representations can lead to clinical misinterpretation, loss of clinician trust, and potential patient safety risks. 

This enhancement establishes an enterprise-grade defense-in-depth architecture covering:
1. **Payload Unpacking & Sanitization (`extract_message_text`):** Intercepts raw LangChain / Gemini chunked list payloads (`[{'type': 'text', ...}]`) and strips base64 cryptographic signatures, joining text parts seamlessly so Markdown tables and headers render without breaks.
2. **System-Wide Incident Logging (`audit_tracker.log_event`):** Assigns a unique incident reference ID (`INC-<timestamp>-<hash>`) to all runtime exceptions (agent errors, API failures, RBAC rejections) and archives complete context in `reports/sessions/` for clinical governance and post-hoc auditing.
3. **Graceful User Notifications & Input Preservation:** Never presents raw stack traces or misleading completion banners. Instead, presents empathetic clinical notice cards with recommended next steps and a **1-click Prompt Draft Restore** button so clinicians never lose their typed queries.
4. **Administrative Incident Review (`GET /api/audit/incidents`):** Exposes an authenticated REST endpoint for compliance officers to inspect historical incident telemetry.
5. **Publication-Grade Markdown & Table Rendering:** Upgrades the Web UI parser to support full clinical data tables, callouts, lists, and typography.

---

## Architecture & Flow

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      Client Web Application / UI                       │
 │  • Text Unpacker: extractTextFromPayload() catches raw list strings     │
 │  • Markdown Formatter: renders tables, lists, and callout alerts       │
 │  • Graceful Error Card: Displays Ref: INC-xxxx & "Restore Draft" button │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP POST /api/chat
 ┌───────────────────────────────────▼────────────────────────────────────┐
 │                       FastAPI Routing & Middleware                     │
 │  • Global Exception Handler -> captures unhandled 500s into audit      │
 │  • RBAC Exception Interceptor -> logs 403s with user role and action   │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ fault_tolerant_agent_execute()
 ┌───────────────────────────────────▼────────────────────────────────────┐
 │                     Agent Orchestration & LLM Layer                    │
 │  • Gemini 3.6 Flash fixed-sampling defaults configured                 │
 │  • LLM responses normalized via extract_message_text()                 │
 │  • Exceptions caught -> logged to reports/sessions/EVENT-*.json        │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Unified Text Extractor (`src/utils/text_extractor.py`)
```python
def extract_message_text(content: Any) -> str:
    """
    Extracts unified plain text/Markdown from an LLM response payload.
    Unpacks lists of chunk dictionaries, decodes stringified Python lists,
    and strips non-text metadata or signature blocks.
    """
```

### 2. Incident Tracker & Draft Preservation (`src/agents/fault_tolerance.py`)
```python
incident_id = f"INC-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}"
audit_tracker.log_event("AGENT_EXECUTION_EXCEPTION", {
    "incident_id": incident_id,
    "thread_id": thread_id,
    "prompt": prompt,
    "error": str(exc),
    "traceback": err_stack[:500]
})
```

### 3. Incident Audit Review API (`src/api/server.py`)
- `GET /api/audit/incidents`: Lists all persisted incidents with timestamps, error types, and execution contexts.

---

## Verification & Testing

Run the dedicated test suite:
```bash
# Windows
.venv\Scripts\python.exe -m pytest tests/test_text_extractor_and_error_handling.py

# Linux / macOS
python -m pytest tests/test_text_extractor_and_error_handling.py
```

Run full regression test suite (all 66 tests passing):
```bash
.venv\Scripts\python.exe -m pytest
```
