# SKILLS.md - Technical Concepts & Skills Handbook

This document serves as your educational handbook and technical reference guide throughout the course.

---

## Key Conceptual Pillars

### 1. Model Context Protocol (MCP)
- **What is it?** An open standard JSON-RPC protocol created by Anthropic that allows AI applications (clients) to securely connect to external tools, databases, and APIs (servers).
- **Transport Types:**
  - `stdio`: Standard input/output stream used for local server processes on the same machine.
  - `SSE` (Server-Sent Events): HTTP streaming protocol used for remote client-server communication over networks.
- **MCP Primitives:**
  - **Resources:** Passive data objects exposed by the server (e.g. `fhir://patient/P101`).
  - **Tools:** Actionable functions callable by the LLM (e.g. `get_lab_results(patient_id="P101")`).
  - **Prompts:** Pre-packaged prompt templates exposed by the server.

---

### 2. HL7 FHIR (Fast Healthcare Interoperability Resources) R4 Standard
- **What is it?** The standard modular data format used across modern healthcare software.
- **Core Resources Used in Platform:**
  - **Patient:** Administrative patient demographics (name, DOB, gender, MRN).
  - **Observation:** Clinical observations such as lab results (HbA1c, Blood Pressure, Cholesterol).
  - **Condition:** Diagnoses, symptoms, or clinical findings (e.g., Type 2 Diabetes, Hypertension).
  - **MedicationRequest:** Orders for medications (e.g., Metformin 500mg, Lisinopril 10mg).
  - **Encounter:** Healthcare interactions (e.g., Inpatient admission, Outpatient visit).

---

### 3. LangGraph Multi-Agent Workflows
- **What is it?** A framework for building stateful, multi-agent AI workflows using graph structures (Nodes & Edges).
- **Core Principles:**
  - **State Channels:** Shared dictionary passing context (e.g. `patient_id`, `fhir_data`, `clinical_flags`, `final_summary`).
  - **Specialized Agents:** Isolated LLM nodes focused on a single task (Ingestion, Analysis, Formatting) to prevent hallucinations and infinite loops.
  - **Human-in-the-Loop (HITL):** Graph `interrupt()` gates that pause execution until a human clinician reviews and attests output.

---

### 4. Dual-LLM PHI Security & Router
- **What is it?** A security architecture designed for HIPAA compliance and Zero Data Retention (ZDR).
- **Mechanism:**
  - **PHI Detector:** Inspects payloads for Protected Health Information (SSNs, names, addresses, MRNs).
  - **Local LLM Route (Ollama Llama-3):** Handles raw PHI queries strictly inside local/private memory.
  - **Cloud LLM Route (Gemini / OpenAI):** Handles complex clinical reasoning using de-identified data.

---

### 5. Enterprise Security & Guardrail Architecture
- **Tri-Fold Security Pipeline:**
  1. **Input Guardrails (Pre-LLM):**
     - **Sensitive Data Masking:** Automated PHI/PII redaction (SSNs, MRNs, Phone numbers, Names) before prompt submission.
     - **Prompt Injection Defense:** Scanning for jailbreak patterns, prompt overrides, or system prompt leaks.
     - **Scope Validation:** Verifying prompts remain strictly within the healthcare/clinical domain.
     - **Content Safety Filter:** Filtering out toxic or unsafe inputs.
  2. **Action Validations (Pre-Execution):**
     - **Schema & Parameter Validation:** Validating tool call arguments against Pydantic schemas before invocation.
     - **Permission Enforcement:** Checking OAuth 2.1 scopes and Role-Based Access Control (RBAC) roles before executing queries.
  3. **Output Guardrails (Post-LLM):**
     - **Hallucination Verification:** Validating generated text assertions against ground-truth FHIR resources.
     - **Sensitive Leakage Masking:** Ensuring unmasked PHI does not leak to unauthorized roles.
     - **Content Safety:** Enforcing clinical safety standards and mandatory medical disclaimers.

---

### 6. Role-Based Access Control (RBAC) & OAuth 2.1
- **What is it?** Enforces data privacy based on the authenticated user's role (e.g. `PHYSICIAN`, `NURSE`, `ADMIN`, `PATIENT`).
- **Field-Level Filtering:** Middleware sanitizes FHIR responses before reaching the LLM (e.g., stripping behavioral health notes from non-psychiatrists).

