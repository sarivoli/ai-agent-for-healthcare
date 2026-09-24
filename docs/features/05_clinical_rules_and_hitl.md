# Feature Specification: Clinical Rules, Confidence Scoring, Prompt-Driven CRUD & HITL Gates

> **Module 6 Feature Documentation**
> **File:** `docs/features/05_clinical_rules_and_hitl.md`
> **Implementation:** `src/rules/rule_engine.py`, `src/db/mock_healthcare_db.py`, `src/mcp_server/server.py`, `src/agents/tools.py`, `src/agents/hitl_agent.py`, `scripts/demo_hitl_approval.py`, `tests/test_hitl_approval.py`

---

## 1. Feature Overview & Purpose

### The Core Problem:
Autonomous AI agents in healthcare must never execute write operations (e.g. creating medication orders, updating patient charts) or finalize critical care plan changes without explicit, authorized human clinician review. Furthermore, raw LLM outputs must be grounded with mathematical confidence scores to prevent unverified recommendations.

### The Solution:
**Module 6** introduces tri-fold clinical governance:
1. **Clinical Rules Engine with Heuristic Confidence Scoring (`ClinicalRuleEngine`)**: Evaluates HEDIS quality benchmarks (CDC HbA1c control, CBP blood pressure control), screening gaps (retinal eye exams, uACR nephropathy tests), and adherence risks. Assigns numerical confidence scores (0.00 to 1.00) based on LOINC code grounding and evidence recency.
2. **Prompt-Driven CRUD Operations**: Exposes FastMCP write tools (`create_medication_order`, `update_patient_note`, `add_care_gap_remediation`) with strict schema validation.
3. **LangGraph Human-in-the-Loop (HITL) Interrupt Gates**: Uses `interrupt()` to pause graph execution whenever write operations or high-confidence care gaps occur, returning `AWAITING_CLINICIAN_APPROVAL`. Graph execution only resumes when an authorized clinician submits an explicit approval or rejection decision.

---

## 2. Architecture & Data Flow

```text
                               User Prompt / CRUD Order
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │      Clinical Rule Engine       │  (src/rules/rule_engine.py)
                         │  - HEDIS CDC & CBP Rules        │
                         │  - Confidence Scores (0.0-1.0)  │
                         └────────────────┬────────────────┘
                                          │
                                [CareGaps & CRUD Actions]
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │   HITL Gate Node (interrupt())  │  (src/agents/hitl_agent.py)
                         │   - Pauses Graph Execution      │
                         │   - Status: PENDING_APPROVAL    │
                         └────────────────┬────────────────┘
                                          │
                            [Clinician Attestation Decision]
                                  /              \
                        APPROVED /                \ REJECTED
                                ▼                  ▼
                   ┌───────────────────┐    ┌───────────────────┐
                   │ Execute CRUD Tool │    │ Log Refusal &     │
                   │ (Write to EHR DB) │    │ Revert Care Plan  │
                   └─────────┬─────────┘    └─────────┬─────────┘
                             │                        │
                             └───────────┬────────────┘
                                         │
                                         ▼
                         ┌─────────────────────────────────┐
                         │    Synthesize Attested Summary  │
                         └─────────────────────────────────┘
```

---

## 3. Interfaces & Data Schemas

### 3.1 `CareGapItem` & `ClinicalRuleEvaluationResult` Models
```python
class CareGapItem(BaseModel):
    gap_id: str
    title: str
    severity: str  # 'HIGH' | 'MEDIUM' | 'LOW'
    confidence_score: float  # 0.00 to 1.00
    evidence_sources: List[str]
    recommendation: str
    requires_hitl_approval: bool = True

class ClinicalRuleEvaluationResult(BaseModel):
    active_diagnoses: List[str]
    quality_metrics: List[HEDISQualityMetric]
    care_gaps: List[CareGapItem]
    adherence_risks: List[str]
    requires_clinician_attestation: bool
    overall_confidence_score: float
```

### 3.2 FastMCP Prompt-Driven CRUD Tools
- `create_medication_order(patient_id, drug_name, dosage, frequency)`
- `update_patient_note(patient_id, note_content, author)`
- `add_care_gap_remediation(patient_id, gap_id, action_taken)`

---

## 4. Execution & Verification

### Run Milestone Demo (Cross-Platform):
```bash
# Windows PowerShell
.venv\Scripts\python.exe scripts/demo_hitl_approval.py --mock

# Linux / macOS
.venv/bin/python3 scripts/demo_hitl_approval.py --mock
```

### Run Unit Tests:
```bash
# Module 6 Tests
.venv\Scripts\python.exe -m pytest tests/test_hitl_approval.py

# All Repository Tests (51 tests)
.venv\Scripts\python.exe -m pytest tests/
```

---

## 5. Verification Results
- **Unit Tests:** 5 passed in `tests/test_hitl_approval.py`.
- **Full Suite:** 51 passed across `tests/`.
- **Confidence Scoring:** 89.0% overall rule confidence calculated across LOINC-grounded lab observations and screening registries.
- **HITL Interrupt:** Verified pause (`PENDING_APPROVAL`) and dual branch execution (Approval -> DB Write commit vs Rejection -> Cancellation).
