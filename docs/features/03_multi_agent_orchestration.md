# Feature Specification: Multi-Agent Architecture & Specialized Roles

> **Module 4 Feature Documentation**
> **File:** `docs/features/03_multi_agent_orchestration.md`
> **Implementation:** `src/agents/multi_agent.py`, `scripts/demo_multi_agent.py`, `tests/test_multi_agent.py`

---

## 1. Feature Overview & Purpose

### The Core Problem:
In complex healthcare scenarios, a single AI agent tasked with retrieving data, conducting clinical rule evaluations, verifying HEDIS quality metrics, and synthesizing persona-tailored summaries is prone to context distortion, hallucinated metrics, and infinite tool-invocation loops.

### The Solution:
**Module 4 Multi-Agent Architecture** segregates clinical processing into isolated, specialized LangGraph agent nodes:
1. **Data Ingestion Agent (`DataIngestionAgent`)**: Autonomously invokes FastMCP tools to fetch and aggregate raw FHIR records (demographics, labs, medications, notes).
2. **Clinical Analyst Agent (`ClinicalAnalystAgent`)**: Evaluates chronic disease parameters, HEDIS quality benchmarks (CDC HbA1c control, CBP blood pressure control), medication adherence risks, and overdue screenings.
3. **Summarization Agent (`SummarizationAgent`)**: Formats persona-tailored summaries (`physician`, `patient`, `coordinator`) combining raw data and analyst findings.
4. **Supervisor Graph Orchestrator**: Manages state transitions and zero-token perimeter security guardrails.

---

## 2. Architecture & Data Flow

```text
                                User Prompt
                                     │
                                     ▼
                      ┌─────────────────────────────┐
                      │    MultiAgentState Schema   │
                      │  - messages: Sequence       │
                      │  - patient_id: str          │
                      │  - summary_persona: str     │
                      │  - raw_fhir_data: Dict      │
                      │  - clinical_analysis: Dict  │
                      │  - final_summary: str       │
                      └──────────────┬──────────────┘
                                     │
                                     ▼
                        ┌───────────────────────────┐
                        │   input_guardrail Node    │
                        │ (Zero-Token Scan Defense) │
                        └────────────┬──────────────┘
                                     │
                             [guardrail_status]
                               /           \
                     PASSED   /             \   BLOCKED (Adversarial)
                             ▼               ▼
                   ┌───────────────────┐     END (0 tokens consumed)
                   │  quota_gate Node  │
                   └─────────┬─────────┘
                             │
                      [quota_status]
                        /         \
              ACTIVE   /           \   LIMIT_EXCEEDED
                      ▼             ▼
          ┌───────────────────────┐ END (Closure Notice)
          │ DataIngestionAgent    │
          │ (Executes MCP Tools)  │
          └───────────┬───────────┘
                      │ raw_fhir_data
                      ▼
          ┌───────────────────────┐
          │ ClinicalAnalystAgent  │
          │ (HEDIS Care Gap Rules)│
          └───────────┬───────────┘
                      │ clinical_analysis
                      ▼
          ┌───────────────────────┐
          │ SummarizationAgent    │
          │ (Persona Formatter)   │
          └───────────┬───────────┘
                      │ final_summary
                      ▼
          ┌───────────────────────┐
          │ synthesize_audit Node │
          │ (Telemetry & Audits)  │
          └───────────┬───────────┘
                      │
                      ▼
                     END
```

---

## 3. State Schema & Interface Contracts

### 3.1 `MultiAgentState` TypedDict
```python
class MultiAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    patient_id: Optional[str]
    summary_persona: str  # 'physician' | 'patient' | 'coordinator'
    raw_fhir_data: Dict[str, Any]
    clinical_analysis: Dict[str, Any]
    final_summary: Optional[str]
    user_id: str
    role: str
    session_id: str
    department: Optional[str]
    quota_status: str
    guardrail_status: str
    telemetry_audit: Optional[Dict[str, Any]]
```

### 3.2 Clinical Care Gap Rules Evaluated
- **HEDIS CDC Measure (HbA1c Control):** Evaluates HbA1c values. If > 8.0%, flags `SUBOPTIMAL`; if > 9.0%, flags `FAIL (POOR_CONTROL)`.
- **HEDIS CBP Measure (Blood Pressure Control):** Evaluates Systolic BP. If >= 140 mmHg, flags `SUBOPTIMAL`.
- **Screening Care Gaps:** Flags overdue annual diabetic dilated eye exam and urine uACR nephropathy check.
- **Medication Adherence Risks:** Extracts reported GI intolerance from physician notes (e.g. skipped metformin).

---

## 4. Execution & Verification

### Run Milestone Demo (Cross-Platform):
```bash
# Windows PowerShell
.venv\Scripts\python.exe scripts/demo_multi_agent.py --mock

# Linux / macOS
.venv/bin/python3 scripts/demo_multi_agent.py --mock
```

### Run Unit Tests:
```bash
# Module 4 Tests
.venv\Scripts\python.exe -m pytest tests/test_multi_agent.py

# All Platform Tests (41 tests)
.venv\Scripts\python.exe -m pytest tests/
```

---

## 5. Verification Results
- **Unit Tests:** 5 passed in `tests/test_multi_agent.py`.
- **Full Suite:** 41 passed across `tests/`.
- **Evidence Grounding:** 100.0% verification score across demographic, lab, and medication assertions.
- **Perimeter Defense:** 0 tokens consumed on prompt injection attempts.
