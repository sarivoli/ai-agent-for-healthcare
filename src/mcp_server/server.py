"""
Healthcare MCP Server using FastMCP Python SDK.
Exposes clinical tools for FHIR Demographics, Lab Results, Medications, and Clinical Notes.
"""

import json
from typing import Optional, Any
from mcp.server.fastmcp import FastMCP
from src.db.mock_healthcare_db import db
from src.security.action_validator import validate_patient_id, ActionValidationError

# Initialize FastMCP Server
mcp_server = FastMCP(
    "healthcare-mcp-server",
    instructions="Provides enterprise healthcare data access via standard FHIR R4 resources and clinical tools."
)


@mcp_server.tool(
    name="get_patient_demographics",
    description="Retrieves FHIR R4 normalized patient demographics, MRN, name, DOB, and active conditions for a given patient_id."
)
def get_patient_demographics(patient_id: str) -> str:
    """Action Guardrail: Validates patient_id before querying database."""
    try:
        clean_id = validate_patient_id(patient_id)
        bundle_data = db.get_patient(clean_id)
        if not bundle_data:
            return json.dumps({"status": "error", "message": f"Patient with ID '{clean_id}' not found."})
        return json.dumps({"status": "success", "data": bundle_data}, indent=2)
    except ActionValidationError as e:
        return json.dumps({"status": "validation_error", "message": str(e)})


@mcp_server.tool(
    name="get_lab_results",
    description="Retrieves LOINC-coded lab observations (e.g. HbA1c, Blood Pressure, Cholesterol) for a given patient_id."
)
def get_lab_results(patient_id: str, test_name: Optional[str] = None) -> str:
    try:
        clean_id = validate_patient_id(patient_id)
        labs = db.get_lab_results(clean_id, test_name=test_name)
        return json.dumps({"status": "success", "patient_id": clean_id, "labs": labs}, indent=2)
    except ActionValidationError as e:
        return json.dumps({"status": "validation_error", "message": str(e)})


@mcp_server.tool(
    name="get_medications",
    description="Retrieves active prescription orders and RxNorm codes for a given patient_id."
)
def get_medications(patient_id: str) -> str:
    try:
        clean_id = validate_patient_id(patient_id)
        meds = db.get_medications(clean_id)
        return json.dumps({"status": "success", "patient_id": clean_id, "medications": meds}, indent=2)
    except ActionValidationError as e:
        return json.dumps({"status": "validation_error", "message": str(e)})


@mcp_server.tool(
    name="get_clinical_notes",
    description="Retrieves physician progress notes, clinical observations, and exam notes for a given patient_id."
)
def get_clinical_notes(patient_id: str) -> str:
    try:
        clean_id = validate_patient_id(patient_id)
        notes = db.get_clinical_notes(clean_id)
        return json.dumps({"status": "success", "patient_id": clean_id, "clinical_notes": notes}, indent=2)
    except ActionValidationError as e:
        return json.dumps({"status": "validation_error", "message": str(e)})


@mcp_server.tool(
    name="create_medication_order",
    description="Prompt-driven CRUD: Creates a new medication prescription order for a given patient_id."
)
def create_medication_order(patient_id: str, drug_name: str, dosage: str, frequency: str = "daily") -> str:
    try:
        clean_id = validate_patient_id(patient_id)
        res = db.create_medication_order(clean_id, drug_name, dosage, frequency)
        return json.dumps(res, indent=2)
    except ActionValidationError as e:
        return json.dumps({"status": "validation_error", "message": str(e)})


@mcp_server.tool(
    name="update_patient_note",
    description="Prompt-driven CRUD: Appends a new physician progress note or clinical update for a given patient_id."
)
def update_patient_note(patient_id: str, note_content: str, author: str = "Attending Physician, MD") -> str:
    try:
        clean_id = validate_patient_id(patient_id)
        res = db.update_patient_note(clean_id, note_content, author)
        return json.dumps(res, indent=2)
    except ActionValidationError as e:
        return json.dumps({"status": "validation_error", "message": str(e)})


@mcp_server.tool(
    name="add_care_gap_remediation",
    description="Prompt-driven CRUD: Documents action taken to remediate a clinical care gap for a patient_id."
)
def add_care_gap_remediation(patient_id: str, gap_id: str, action_taken: str) -> str:
    try:
        clean_id = validate_patient_id(patient_id)
        res = db.add_care_gap_remediation(clean_id, gap_id, action_taken)
        return json.dumps(res, indent=2)
    except ActionValidationError as e:
        return json.dumps({"status": "validation_error", "message": str(e)})


@mcp_server.tool(
    name="add_lab_result",
    description="Prompt-driven CRUD: Records a new clinical lab result or observation for a patient_id."
)
def add_lab_result(patient_id: str, test_name: str, value: Any, unit: str = "", loinc: str = "") -> str:
    try:
        clean_id = validate_patient_id(patient_id)
        res = db.add_lab_result(clean_id, test_name, value, unit, loinc)
        return json.dumps(res, indent=2)
    except ActionValidationError as e:
        return json.dumps({"status": "validation_error", "message": str(e)})


if __name__ == "__main__":
    mcp_server.run()
