# Feature Specification: Dual-LLM Routing & PHI Protection

> **Module 5 Feature Documentation**
> **File:** `docs/features/04_dual_llm_phi_router.md`
> **Implementation:** `src/router/phi_classifier.py`, `src/router/llm_providers.py`, `src/router/dual_llm_router.py`, `scripts/demo_dual_llm_router.py`, `tests/test_dual_llm_router.py`

---

## 1. Feature Overview & Purpose

### The Core Problem:
Cloud AI APIs (e.g. Gemini, OpenAI) offer massive reasoning capacity but pose severe HIPAA compliance risks if raw Protected Health Information (PHI)—such as patient names, SSNs, MRNs, phone numbers, or dates of birth—is exfiltrated to third-party servers without Zero Data Retention (ZDR) agreements.

### The Solution:
The **Dual-LLM Privacy Router** enforces real-time privacy classification and dynamic routing:
1. **PHI Classifier Engine (`PHIClassifierEngine`)**: Real-time scanner evaluating 18 HIPAA categories, generating sensitivity scores (0.0 to 1.0) and managing token redaction maps.
2. **Local LLM Route (`LOCAL_PHI_ROUTE`)**: Directs raw PHI queries to a **Local LLM** (Ollama Llama-3 / Host Privacy Node) running strictly inside local host memory to guarantee **Zero Data Retention (ZDR)**.
3. **Cloud LLM Route (`CLOUD_DEIDENTIFIED_ROUTE`)**: Directs clean queries to **Cloud LLM** (Gemini 3.6 Flash).
4. **De-identification Proxy**: Supports automated token replacement (`[PATIENT_NAME_1]`, `[MRN_1]`), sending de-identified payloads to Cloud LLMs and re-identifying tokens upon return.

---

## 2. Architecture & Data Flow

```text
                                User Clinical Query
                                         │
                                         ▼
                           ┌───────────────────────────┐
                           │   PHI Classifier Engine   │  (src/router/phi_classifier.py)
                           │   - SSN, MRN, Name, Phone │
                           │   - Sensitivity Score     │
                           └─────────────┬─────────────┘
                                         │
                                [PHIScanResult]
                                  /         \
                 Contains PHI?   /           \  Clean Payload (No PHI)
                                ▼             ▼
       ┌──────────────────────────────┐     ┌──────────────────────────────┐
       │ LOCAL LLM ROUTE              │     │ CLOUD LLM ROUTE              │
       │ (Ollama Llama-3 / Local Node)│     │ (Gemini 3.6 Flash / Cloud)   │
       │ Zero Data Retention (ZDR)     │     │ High-Level Reasoning         │
       └──────────────┬───────────────┘     └──────────────┬───────────────┘
                      │                                    │
                      └──────────────────┬─────────────────┘
                                         │
                                         ▼
                           ┌───────────────────────────┐
                           │   DualLLMRoutingResult    │
                           │   - Route Selected        │
                           │   - ZDR Status            │
                           │   - Telemetry Audit       │
                           └───────────────────────────┘
```

---

## 3. Interfaces & Data Schemas

### 3.1 `PHIScanResult` Model
```python
class PHIScanResult(BaseModel):
    contains_phi: bool
    detected_categories: List[str]
    redacted_text: str
    phi_token_map: Dict[str, str]
    sensitivity_score: float
```

### 3.2 `DualLLMRoutingResult` Model
```python
class DualLLMRoutingResult(BaseModel):
    session_id: str
    route_selected: str  # 'LOCAL_PHI_ROUTE' | 'CLOUD_DEIDENTIFIED_ROUTE'
    zdr_enforced: bool
    phi_scan: PHIScanResult
    deidentification_proxy_used: bool
    raw_response: str
    final_response: str
    latency_seconds: float
```

---

## 4. Execution & Verification

### Run Milestone Demo (Cross-Platform):
```bash
# Windows PowerShell
.venv\Scripts\python.exe scripts/demo_dual_llm_router.py --mock

# Linux / macOS
.venv/bin/python3 scripts/demo_dual_llm_router.py --mock
```

### Run Unit Tests:
```bash
# Module 5 Tests
.venv\Scripts\python.exe -m pytest tests/test_dual_llm_router.py

# All Repository Tests (46 tests)
.venv\Scripts\python.exe -m pytest tests/
```

---

## 5. Verification Results
- **Unit Tests:** 5 passed in `tests/test_dual_llm_router.py`.
- **Full Suite:** 46 passed across `tests/`.
- **PHI Detection:** 100.0% detection rate across SSNs, MRNs, phone numbers, DOBs, and patient names.
- **Zero Data Retention:** Verified ZDR local route enforcement for sensitive payloads.
