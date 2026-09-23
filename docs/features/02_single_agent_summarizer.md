# Feature Specification: LangGraph Single-Agent Clinical Summarizer (`02_single_agent_summarizer.md`)

## 1. Overview & Business Value
The **Single-Agent Clinical Summarizer** (`src/agents/single_agent.py`) introduces autonomous clinical reasoning into the platform. In Module 2, tools had to be triggered manually. In Module 3, a **LangGraph ReAct agent** inspects unstructured user queries, autonomously determines which MCP clinical tools to invoke, retrieves FHIR R4 and clinical note data, and synthesizes clinical reports customized to specific stakeholder personas (Physician SOAP Brief, Patient-Friendly Discharge Guide, and Care Coordinator Audit).

---

## 2. Architectural Analysis: Why LangGraph Over Alternatives?

When designing autonomous clinical agents, three architectural approaches were evaluated:

| Architectural Pattern | How It Works | Strengths | Major Limitations in Healthcare | Decision |
| :--- | :--- | :--- | :--- | :--- |
| **1. Linear Prompt Chain (LangChain `LLMChain`)** | Fixed sequence: Prompt -> Tool -> Summary. | Simple to write, predictable. | Cannot adapt if tool inputs need dynamic refinement; cannot loop if data is incomplete. | ❌ Rejected |
| **2. Legacy Agent Executor (`initialize_agent`)** | Black-box while-loop managing scratchpad. | Quick prototype. | Hard to intercept state; impossible to inject clinical guardrails mid-step or inspect intermediate checkpoints. | ❌ Deprecated |
| **3. LangGraph State Machine (`StateGraph`)** | Cyclic directed graph with typed state, deterministic node boundaries, and conditional routing. | **Full state transparency**, cyclic tool-calling, human-in-the-loop ready, clear validation checkpoints. | Requires explicit state definition. | ✅ **Selected Best Option** |

### Why `StateGraph` is the Best Choice for Healthcare:
1. **Auditability & Observability:** Every state transition (`agent` -> `tools` -> `synthesize`) records the exact prompt, arguments, and FHIR response in the state history.
2. **Deterministic Safety Gaps:** We can place guardrails (action validators) before and after each node transition.
3. **Multi-Agent Readiness:** The `StateGraph` built here serves as the exact foundation for Module 4 (Supervisor multi-agent hierarchy).

---

## 3. Architecture & State Transition Diagram

```text
                                  User Query
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │  ClinicalAgentState (Typed)   │
                       │  - messages: Sequence[BaseMsg]│
                       │  - patient_id: Optional[str]  │
                       │  - summary_persona: str       │
                       │  - final_summary: str         │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                             ┌───────────────────┐
                             │    agent Node     │ ◄──────────────────┐
                             │  (LLM Reasoning)  │                    │
                             └─────────┬─────────┘                    │
                                       │                              │
                              [tools_condition]                       │
                                /             \                       │
                      Has Tool Calls?      No Tool Calls (Finished)   │
                              /                 \                     │
                             ▼                   ▼                    │
                   ┌───────────────────┐     ┌───────────────────┐    │
                   │    tools Node     │     │  synthesize Node  │    │
                   │ (ToolNode executing│     │(Applies Persona   │    │
                   │  MCP FastMCP tools│     │ Template: SOAP /  │    │
                   │  with Guardrails) │     │ Patient Guide)    │    │
                   └─────────┬─────────┘     └─────────┬─────────┘    │
                             │                         │              │
                             └─────────────────────────┴──────────────┘
                                                       │
                                                       ▼
                                                      END
```

---

## 4. Key Subsystems & Implementation Details

### A. Dual LLM Execution Strategy (Cloud vs. Offline Fallback)
To satisfy enterprise flexibility and testing requirements, the system supports a dual provider strategy controlled via `.env`:
- **Live Gemini API:** Powered by `langchain-google-genai` using the modern `gemini-3.6-flash` endpoint with temperature set to `0.1` for grounded clinical reasoning.
- **Deterministic Clinical Mock LLM (`DeterministicClinicalChatModel`):** A custom `BaseChatModel` implementation that autonomously issues realistic tool calls on turn 1 and formats accurate clinical syntheses on turn 2. This enables zero-cost testing, CI/CD pipeline automation, and offline operation.

### B. Configurable Persona Prompt Pipeline (`src/agents/prompts.py`)
Different clinical consumers require different representations of the same health data:
1. **`physician` (SOAP Brief):**
   - **S (Subjective):** Patient complaints and physician notes.
   - **O (Objective):** LOINC lab results (HbA1c 8.4%, BP 142/90 mmHg).
   - **A (Assessment):** ICD-10 conditions (`E11.9`, `I10`) and glycemic control status.
   - **P (Plan):** RxNorm medications (`Metformin 1000mg`, `Lisinopril 10mg`) and screening care gaps.
2. **`patient` (Personal Health Summary & Discharge Guide):**
   - 6th-grade reading level.
   - Plain English translations of lab terms ("sugar levels" vs "HbA1c").
   - Clear daily medication timing and gastrointestinal comfort instructions.
   - Warning red flags for when to call emergency or primary care.
3. **`coordinator` (Quality & Gap Audit):**
   - Focuses on HEDIS quality metrics, chronic disease registries, and screening compliance.

### C. Tool Adapters with Action Guardrails (`src/agents/tools.py`)
Wraps the 4 FastMCP tools using LangChain `@tool`:
- `get_patient_demographics(patient_id: str)`
- `get_lab_results(patient_id: str, test_name: Optional[str] = None)`
- `get_medications(patient_id: str)`
- `get_clinical_notes(patient_id: str)`
Every tool passes arguments through `validate_patient_id()` from `src/security/action_validator.py` before touching the data layer.

### D. Role-Based Token Quota & Grace Buffer Governance (`src/security/quota_manager.py`)
To scale the platform in an enterprise multi-tenant setting, we enforce configurable token quotas based on user roles and patient tiers:
- **`supervisor`:** 15,000 tokens (High-capacity clinical management & quality audits)
- **`clinician`:** 8,000 tokens (Attending physician diagnosis & chart reviews)
- **`patient_vip`:** 5,000 tokens (Elevated concierge conversational allowance)
- **`patient_standard`:** 2,000 tokens (Standard patient discharge inquiry allowance)
- **20% Grace Buffer:** When an in-progress conversation crosses the base threshold, the agent does NOT abruptly truncate mid-sentence. It completes the synthesis, appends an advisory banner, and enters `GRACE_PERIOD`.
- **Professional Closure Messages:** When the grace limit is exceeded (`LIMIT_EXCEEDED`), the `quota_gate` node intercepts the query and returns a courteous, professional next-steps notice (e.g. directing patients to primary care lines or portal messaging).

### E. Extensible Strategy Pattern for Quotas (`src/security/quota_manager.py`)
Hospitals require diverse business rules (e.g., ICU clinicians need higher conversational budgets than outpatient nurses; critical acuity alerts need emergency multipliers). Rather than hardcoding rules into agent nodes, the governance engine implements the **Strategy Pattern**:
- **`BaseQuotaStrategy` (ABC):** Defines the standard interface `calculate_quota(context: QuotaContext) -> Tuple[int, int]`.
- **`RoleBasedQuotaStrategy`:** Standard default policy driven by user roles and `.env` overrides.
- **`DepartmentTierQuotaStrategy`:** Applies departmental multipliers (`icu`: 2.0x, `emergency`: 1.75x, `oncology`: 1.5x, `cardiology`: 1.3x).
- **`CustomRuleQuotaStrategy`:** Enables registering custom enterprise lambdas (e.g., Code Blue or patient acuity overrides) dynamically.
- **Runtime Swapping:** `quota_manager.set_strategy(...)` permits dynamic policy injection without changing a single line of agent graph code.

### F. Perimeter Defense & Input Guardrails (`src/security/input_guardrails.py`)
To prevent adversarial prompt injection, jailbreak attempts, or data exfiltration:
1. **Zero-Token Perimeter Defense:** Scans user prompts before model invocation or tool execution. Malicious queries are terminated at the graph entry boundary, burning 0 LLM tokens.
2. **Jailbreak Interception:** Blocks phrases attempting to bypass safety rules (`ignore previous instructions`, `DAN mode`, `developer mode`, `system override`).
3. **Telemetry & System Exfiltration Defense:** Blocks probes seeking hidden system prompts, API keys, database credentials, or internal token metrics (`show me token monitor`, `reveal system prompt`).
4. **Out-of-Band Telemetry Isolation:** Statistical metrics, costs, and quota counters are maintained strictly in Python memory and serialized to disk files (`reports/sessions/`); they are never injected into the LLM context or exposed through tool schemas, rendering them inaccessible to conversational probing.

### G. Telemetry, Token Meter & Evidence Grounding Audit (`src/security/audit_tracker.py`)
Every LangGraph interaction produces comprehensive audit metrics:
1. **Token Meter:** Captures prompt, completion, total tokens, and estimates model API costs.
2. **Execution Latency:** Measures end-to-end graph traversal duration.
3. **EHR Grounding Audit:** Directly cross-references synthesized claims against retrieved FHIR resources to verify that lab observations (`8.4%`, `142 mmHg`), patient identifiers, and medications are 100% grounded (zero hallucination verification).
4. **Session Archival & Retrieval:** Serializes every interaction to `reports/sessions/<session_id>.json` and human-readable Markdown, with a dedicated lookup API (`audit_tracker.get_session_audit_report(session_id)`).

---

## 5. Execution & Verification

### Running the Milestone Demo:
```powershell
# Windows (Live Gemini or default configured mode with Telemetry, Guardrails & Quotas):
.venv\Scripts\python.exe scripts\demo_single_agent.py

# Windows (Forced Offline Deterministic Mock):
.venv\Scripts\python.exe scripts\demo_single_agent.py --mock

# Role-specific run (e.g. patient_vip or supervisor):
.venv\Scripts\python.exe scripts\demo_single_agent.py --role patient_vip --mock

# Linux / macOS:
.venv/bin/python3 scripts/demo_single_agent.py
.venv/bin/python3 scripts/demo_single_agent.py --mock
```

### Running Automated PyTest Suite:
```powershell
# Windows (Module 3 + Governance + Guardrails tests):
.venv\Scripts\python.exe -m pytest tests/test_single_agent.py tests/test_audit_and_quota.py tests/test_input_guardrails.py

# Windows (All 36 platform tests across all modules):
.venv\Scripts\python.exe -m pytest tests/

# Linux / macOS:
.venv/bin/python3 -m pytest tests/
```

