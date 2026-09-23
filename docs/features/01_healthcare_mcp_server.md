# Feature Specification: Healthcare FastMCP Server (`01_healthcare_mcp_server.md`)

## 1. Overview & Purpose
The Healthcare MCP Server (`src/mcp_server/server.py`) provides standardized access to clinical data using the Model Context Protocol (MCP) JSON-RPC standard. It exposes tools for retrieving patient demographics (FHIR bundles), lab observations, medication requests, and physician notes.

---

## 2. Architecture & Data Flow

```text
 ┌──────────────────────┐          Action Validation (Guardrail)          ┌──────────────────────┐
 │   MCP Client / Agent │ ──── JSON-RPC Tool Call (patient_id) ────────► │ Action Parameter     │
 └──────────────────────┘                                                │ Validation Engine    │
                                                                         └──────────┬───────────┘
                                                                                    │ Sanitized
 ┌──────────────────────┐                                                           ▼
 │ Mock Healthcare DB   │ ◄─── Normalized FHIR Query ───────────────────────── ┌──────────────────────┐
 │ (SQLite / EHR JSON)  │                                                        │ FastMCP Server       │
 └──────────────────────┘                                                        └──────────────────────┘
```

---

## 3. Registered Tool Interfaces

### `get_patient_demographics(patient_id: str)`
- **Description:** Returns FHIR R4 Bundle containing normalized `Patient`, `Condition`, and `Encounter` resources.
- **Action Guardrail:** Validates `patient_id` format (alphanumeric + hyphens, max 20 chars).

### `get_lab_results(patient_id: str, test_name: Optional[str] = None)`
- **Description:** Returns LOINC-coded lab observations (e.g. HbA1c, Blood Pressure, Cholesterol).

### `get_medications(patient_id: str)`
- **Description:** Returns active prescription orders with RxNorm codes.

### `get_clinical_notes(patient_id: str)`
- **Description:** Returns physician progress notes and clinical observations.

---

## 4. Execution & Validation

### Run Milestone Demo:
- **Windows:** `.venv\Scripts\python.exe -m scripts.demo_mcp_client`
- **Linux/macOS:** `.venv/bin/python3 -m scripts.demo_mcp_client`

### Run PyTest Suite:
- **Windows:** `.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py`
- **Linux/macOS:** `.venv/bin/python3 -m pytest tests/test_mcp_server.py`
