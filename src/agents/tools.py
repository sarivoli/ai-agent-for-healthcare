"""
LangChain Tool Adapters for Healthcare MCP Server.
Binds clinical data tools with parameter schema validation to LangChain/LangGraph agents.
"""

import json
from typing import Optional
from langchain_core.tools import tool
from src.db.mock_healthcare_db import db
from src.security.action_validator import validate_patient_id, ActionValidationError


@tool
def get_patient_demographics(patient_id: str) -> str:
    """
    Retrieves FHIR R4 normalized patient demographics, MRN, official name, DOB, and active conditions.
    Args:
        patient_id: Alphanumeric patient identifier (e.g., 'P101').
    """
    try:
        clean_id = validate_patient_id(patient_id)
        bundle_data = db.get_patient(clean_id)
        if not bundle_data:
            return json.dumps({"status": "error", "message": f"Patient with ID '{clean_id}' not found."})
        return json.dumps({"status": "success", "data": bundle_data})
    except ActionValidationError as e:
        return json.dumps({"status": "validation_error", "message": str(e)})


@tool
def get_lab_results(patient_id: str, test_name: Optional[str] = None) -> str:
    """
    Retrieves LOINC-coded laboratory observations (e.g. HbA1c, Blood Pressure, Cholesterol) for a patient.
    Args:
        patient_id: Alphanumeric patient identifier (e.g., 'P101').
        test_name: Optional test filter (e.g., 'Hemoglobin A1c').
    """
    try:
        clean_id = validate_patient_id(patient_id)
        labs = db.get_lab_results(clean_id, test_name=test_name)
        return json.dumps({"status": "success", "patient_id": clean_id, "labs": labs})
    except ActionValidationError as e:
        return json.dumps({"status": "validation_error", "message": str(e)})


@tool
def get_medications(patient_id: str) -> str:
    """
    Retrieves active prescription orders and RxNorm codes for a given patient.
    Args:
        patient_id: Alphanumeric patient identifier (e.g., 'P101').
    """
    try:
        clean_id = validate_patient_id(patient_id)
        meds = db.get_medications(clean_id)
        return json.dumps({"status": "success", "patient_id": clean_id, "medications": meds})
    except ActionValidationError as e:
        return json.dumps({"status": "validation_error", "message": str(e)})


@tool
def get_clinical_notes(patient_id: str) -> str:
    """
    Retrieves physician progress notes, clinical observations, and exam notes for a patient.
    Args:
        patient_id: Alphanumeric patient identifier (e.g., 'P101').
    """
    try:
        clean_id = validate_patient_id(patient_id)
        notes = db.get_clinical_notes(clean_id)
        return json.dumps({"status": "success", "patient_id": clean_id, "clinical_notes": notes})
    except ActionValidationError as e:
        return json.dumps({"status": "validation_error", "message": str(e)})


# List of all available clinical tools for the agent
CLINICAL_TOOLS = [
    get_patient_demographics,
    get_lab_results,
    get_medications,
    get_clinical_notes
]
