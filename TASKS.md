# TASKS.md - Course Task List & Session Progress Log

## Active Task Overview

- **Current Active Module:** Module 5: Dual-LLM Routing & PHI Protection (Completed - Ready for Module 6)
- **Overall Progress:** 5 / 7 Modules Completed

---

## Detailed Task Checklist

### Setup & Infrastructure
- [x] Create workspace tracking system (`GEMINI.md`, `PROJECTS.md`, `TASKS.md`, `SKILLS.md`, `ARCHITECTURE.md`, `docs/features/README.md`)
- [x] Initialize Python environment and dependencies (`mcp<2.0.0`, `pydantic`, `pytest`, `python-dotenv`, `langchain`, `langgraph`)

### Module 1: MCP Foundations & Healthcare Interoperability
- [x] Step 1.1: Learn & Document FHIR R4 Core Standards (`Patient`, `Observation`, `Condition`, `MedicationRequest`, `Encounter`) in `SKILLS.md`
- [x] Step 1.2: Create raw vendor mock data & FHIR normalization utility (`src/fhir/schemas.py`, `src/fhir/normalizer.py`)
- [x] Step 1.3: Build & run Module 1 Working Milestone Demo (`tests/test_fhir_normalization.py`)
- [x] Step 1.4: Document Module 1 completion & log session state

### Module 2: Local Development Setup & MCP Server Construction
- [x] Step 2.1: Create mock Healthcare Database (`src/db/mock_healthcare_db.py`)
- [x] Step 2.2: Build FastMCP Healthcare Server (`src/mcp_server/server.py`) exposing 4 clinical tools
- [x] Step 2.3: Build stdio MCP client test harness (`scripts/demo_mcp_client.py`) & run Module 2 Working Milestone Demo
- [x] Step 2.4: Write Feature Documentation (`docs/features/01_healthcare_mcp_server.md`) & update `ARCHITECTURE.md`

### Module 3: LangChain & LangGraph Single-Agent Integration
- [x] Step 3.1: Build Single-Agent Orchestrator binding MCP tools to LLM (`src/agents/tools.py`, `src/agents/single_agent.py`)
- [x] Step 3.2: Create Configurable Patient Summarizer prompt pipeline (`src/agents/prompts.py`)
- [x] Step 3.3: Run Module 3 Working Milestone Demo (`scripts/demo_single_agent.py`, `tests/test_single_agent.py`)
- [x] Step 3.4: Write Feature Documentation (`docs/features/02_single_agent_summarizer.md`) & Course Guide sync (`docs/COURSE_GUIDE.md`)

### Module 4: Multi-Agent Architecture & Specialized Roles
- [x] Step 4.1: Build Data Ingestion Agent (MCP FHIR retriever) (`src/agents/multi_agent.py`)
- [x] Step 4.2: Build Clinical Analyst Agent (care gap & HEDIS rule checker) (`src/agents/multi_agent.py`)
- [x] Step 4.3: Build Summarization Agent (custom template formatter) (`src/agents/multi_agent.py`)
- [x] Step 4.4: Build Supervisor Graph orchestrating state handoffs (`src/agents/multi_agent.py`)
- [x] Step 4.5: Run Module 4 Working Milestone Demo (`scripts/demo_multi_agent.py`, `tests/test_multi_agent.py`)
- [x] Step 4.6: Write Feature Documentation (`docs/features/03_multi_agent_orchestration.md`) & Course Guide sync (`docs/COURSE_GUIDE.md`)

### Module 5: Dual-LLM Routing & PHI Protection
- [x] Step 5.1: Build PHI Classifier node (regex + NER privacy evaluator) (`src/router/phi_classifier.py`)
- [x] Step 5.2: Integrate Local LLM provider alongside Cloud LLM (`src/router/llm_providers.py`)
- [x] Step 5.3: Build Dual-LLM router node enforcing Zero Data Retention (ZDR) (`src/router/dual_llm_router.py`)
- [x] Step 5.4: Run Module 5 Working Milestone Demo (`scripts/demo_dual_llm_router.py`, `tests/test_dual_llm_router.py`)
- [x] Step 5.5: Write Feature Documentation (`docs/features/04_dual_llm_phi_router.md`) & Course Guide sync (`docs/COURSE_GUIDE.md`)

### Module 6: Clinical Identification, Confidence Scoring & HITL Gates
- [ ] Step 6.1: Build Rule Engine for Care Gaps with Heuristic Confidence Scores
- [ ] Step 6.2: Build LangGraph HITL interrupt node requiring clinician attestation
- [ ] Step 6.3: Implement Prompt-Driven CRUD Clinical Tools (Create/Update Medication Orders & Patient Notes via MCP)
- [ ] Step 6.4: Run Module 6 Working Milestone Demo (`scripts/demo_hitl_approval.py`)
- [ ] Step 6.5: Write Feature Documentation (`docs/features/05_clinical_rules_and_hitl.md`)

### Module 7: Production Hardening, RBAC, Web UI & Deployment
- [ ] Step 7.1: Implement OAuth 2.1 token verifier & field-level RBAC middleware
- [ ] Step 7.2: Implement LangGraph Session Memory Checkpointer (`MemorySaver` / SQLite state caching) to eliminate redundant DB calls
- [ ] Step 7.3: Implement Fault-Tolerant Input Persistence & Agent Exception Handlers (preventing user input loss on programming errors)
- [ ] Step 7.4: Build FastAPI streaming chat backend (SSE stream)
- [ ] Step 7.5: Build Web Application Client UI
- [ ] Step 7.6: Dockerize platform (`Dockerfile`, `docker-compose.yml`)
- [ ] Step 7.7: Run Module 7 Working Milestone Demo (`docker-compose up` & Web App verification)
- [ ] Step 7.8: Write Feature Documentation (`docs/features/06_production_hardening_and_ui.md`) & Final Course Review

---

## Session History Log

| Session Date | Module / Tasks Worked On | Key Decisions & Deviations | Next Steps |
| :--- | :--- | :--- | :--- |
| **2026-09-20** | Session 1: Tracking Setup & Module 1 | Created tracking system (`GEMINI.md`, `PROJECTS.md`, `TASKS.md`, `SKILLS.md`, `ARCHITECTURE.md`). Completed Module 1 FHIR schemas (`src/fhir/schemas.py`), normalizer (`src/fhir/normalizer.py`), and working milestone demo (`tests/test_fhir_normalization.py`). | Build Module 2: FastMCP Healthcare Server with 4 clinical tools (`src/mcp_server/server.py`). |
| **2026-09-20** | Session 2: Module 2 Completion & Course Guide Sync | Built FastMCP healthcare server (`src/mcp_server/server.py`), action parameter guardrails (`src/security/action_validator.py`), mock DB (`src/db/mock_healthcare_db.py`), client demo (`scripts/demo_mcp_client.py`), and updated `docs/COURSE_GUIDE.md` with complete step-by-step breakdowns and verbatim terminal outputs for Modules 1 & 2. | Ready for Module 3: LangChain & LangGraph Single-Agent Integration. |
| **2026-09-20** | Session 3: Module 3 Single-Agent Implementation | Implemented LangChain `@tool` adapters (`src/agents/tools.py`), multi-persona templates (`src/agents/prompts.py`), and LangGraph ReAct orchestrator (`src/agents/single_agent.py`). Integrated dual-LLM provider support (Live Gemini via `gemini-3.6-flash` + offline deterministic mock). Created milestone demo (`scripts/demo_single_agent.py`), full pytest suite (`tests/test_single_agent.py`), feature doc (`docs/features/02_single_agent_summarizer.md`), and updated `docs/COURSE_GUIDE.md`. | Ready for Module 3 Governance & Security Enhancements. |
| **2026-09-20** | Session 4: Module 3 Enterprise Governance, Guardrails & Quota Strategies | Added Input Guardrail Engine (`src/security/input_guardrails.py`) with zero-token perimeter defense against adversarial jailbreaks & telemetry exfiltrations. Built Extensible Quota Strategy Pattern (`src/security/quota_manager.py`) supporting dynamic department multipliers (e.g. ICU 2.0x), 20% grace buffers, and polite conversation holds. Built Audit Tracker (`src/security/audit_tracker.py`) for EHR evidence grounding and JSON/MD report archival. Added `tests/test_input_guardrails.py` (all 36 tests pass across repo). Updated `scripts/demo_single_agent.py`, `docs/features/02_single_agent_summarizer.md`, and `docs/COURSE_GUIDE.md`. | Strict hold: Awaiting explicit user direction before initiating Module 4. |
| **2026-09-23** | Session 5: Module 4 Multi-Agent Architecture & Specialized Roles | Implemented `MultiAgentState` schema, `DataIngestionAgent`, `ClinicalAnalystAgent` (care gaps & HEDIS CDC/CBP metrics), `SummarizationAgent`, and Supervisor Graph workflow (`src/agents/multi_agent.py`). Built milestone demo (`scripts/demo_multi_agent.py`), unit test suite (`tests/test_multi_agent.py`, 41 total repository tests pass), feature doc (`docs/features/03_multi_agent_orchestration.md`), and updated `docs/COURSE_GUIDE.md`. | Ready for Module 5: Dual-LLM Routing & PHI Protection. |
| **2026-09-23** | Session 6: Module 5 Dual-LLM Routing & PHI Protection | Implemented `PHIClassifierEngine` (`src/router/phi_classifier.py`), `LocalLLMProvider` & `CloudLLMProvider` (`src/router/llm_providers.py`), and `DualLLMRouterNode` (`src/router/dual_llm_router.py`). Enforced Zero Data Retention (ZDR) routing for raw PHI and automated De-identification Proxy roundtrip. Built milestone demo (`scripts/demo_dual_llm_router.py`), unit test suite (`tests/test_dual_llm_router.py`, 46 total repository tests pass), feature doc (`docs/features/04_dual_llm_phi_router.md`), updated `ARCHITECTURE.md` (ADR-005), and updated `docs/COURSE_GUIDE.md`. | Ready for Module 6: Clinical Rules, Confidence Scoring & HITL Gates. |


