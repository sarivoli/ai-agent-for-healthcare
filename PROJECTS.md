# PROJECTS.md - Master Project Specification & Roadmap

## Vision
The **Enterprise Healthcare MCP & Multi-Agent Platform** is a production-grade, secure healthcare AI application. It unifies disparate clinical data sources using the **Model Context Protocol (MCP)**, normalizes raw EHR data into standardized **FHIR R4** resources, orchestrates specialized **LangGraph** agents, dynamically routes sensitive **PHI** to local LLMs while preserving cloud reasoning capabilities, and enforces field-level **RBAC** security.

---

## Technology Stack

| Component | Local Development (Course) | Production Target |
| :--- | :--- | :--- |
| **Language & Core** | Python 3.10+, FastAPI | Python 3.10+, FastAPI |
| **MCP Protocol** | FastMCP SDK via `stdio` | MCP Gateway via `SSE` / mTLS |
| **Data Standard** | FHIR R4 (Pydantic models) | HL7 FHIR v4.0.1 Standard |
| **Agent Framework** | LangChain & LangGraph | LangGraph Cloud / Kubernetes Workers |
| **LLM Execution** | Local (Ollama Llama-3 / Mock Local) & Cloud (Gemini / OpenAI) | Private VPC LLM + Cloud with HIPAA BAA |
| **Security & Auth** | OAuth 2.1 mock verification & RBAC filter | Enterprise IdP (Okta/Ping) + TLS 1.3 |
| **User Interface** | Streaming Web App / FastUI Chat | Embedded SaaS iFrame / Web Component |

---

## Course Module Map & Working Demos

| Module | Title | Working Milestone Demo Script | Feature Doc | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Module 1** | MCP Foundations & FHIR | `python -m tests.test_fhir_normalization` | Standard FHIR R4 Models | ✅ Completed |
| **Module 2** | Local MCP Server | `python -m scripts.demo_mcp_client` | `docs/features/01_healthcare_mcp_server.md` | ✅ Completed |
| **Module 3** | Single-Agent Summarizer | `python -m scripts.demo_single_agent` | `docs/features/02_single_agent_summarizer.md` | ✅ Completed |

| **Module 4** | Multi-Agent Orchestration | `python -m scripts.demo_multi_agent` | `docs/features/03_multi_agent_orchestration.md` | ✅ Completed |
| **Module 5** | Dual-LLM PHI Router | `python -m scripts.demo_dual_llm_router` | `docs/features/04_dual_llm_phi_router.md` | ✅ Completed |
| **Module 6** | Clinical Rules & HITL | `python -m scripts.demo_hitl_approval` | `docs/features/05_clinical_rules_and_hitl.md` | ✅ Completed |
| **Module 7** | Production Hardening & UI | `python -m scripts.demo_production_ui` | `docs/features/06_production_hardening_and_ui.md` | ✅ Completed |

---

## Master Course & Demo Guide
For complete step-by-step teaching notes, code snippets, dual OS terminal commands (Windows & Linux), and expected outputs, refer to [docs/COURSE_GUIDE.md](file:///d:/aiagent/docs/COURSE_GUIDE.md).

---

## Feature Documentation Index

All completed features generate dedicated feature specifications in [docs/features/](file:///d:/aiagent/docs/features/README.md).
- [01_healthcare_mcp_server.md](file:///d:/aiagent/docs/features/01_healthcare_mcp_server.md) *(Pending Module 2)*
- [02_single_agent_summarizer.md](file:///d:/aiagent/docs/features/02_single_agent_summarizer.md) *(Pending Module 3)*
- [03_multi_agent_orchestration.md](file:///d:/aiagent/docs/features/03_multi_agent_orchestration.md) *(Pending Module 4)*
- [04_dual_llm_phi_router.md](file:///d:/aiagent/docs/features/04_dual_llm_phi_router.md) *(Pending Module 5)*
- [05_clinical_rules_and_hitl.md](file:///d:/aiagent/docs/features/05_clinical_rules_and_hitl.md) *(Pending Module 6)*
- [06_production_hardening_and_ui.md](file:///d:/aiagent/docs/features/06_production_hardening_and_ui.md) *(Pending Module 7)*
