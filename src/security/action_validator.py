"""
Action Validation & Parameter Schema Engine.
Validates parameters, types, and constraints before executing tool actions or database queries.
"""

import re
from typing import Dict, Any


class ActionValidationError(Exception):
    """Raised when an action or tool execution parameter fails schema validation."""
    pass


def validate_patient_id(patient_id: str) -> str:
    """
    Validates patient ID parameter format and sanitizes input.
    Expected format: Non-empty string, alphanumeric + hyphens (e.g., 'P101', 'P-102').
    """
    if not patient_id or not isinstance(patient_id, str):
        raise ActionValidationError("Parameter 'patient_id' must be a non-empty string.")
    
    clean_id = patient_id.strip()
    if len(clean_id) > 20:
        raise ActionValidationError(f"Parameter 'patient_id' exceeds maximum length of 20 chars.")
    
    if not re.match(r"^[A-Za-z0-9\-]+$", clean_id):
        raise ActionValidationError(f"Invalid characters in 'patient_id': '{clean_id}'. Only alphanumeric and hyphens allowed.")
    
    return clean_id.upper()


def validate_tool_call_params(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Action Guardrail: Validates input arguments for a specified tool action.
    """
    validated_params = {}
    
    if tool_name in ["get_patient_demographics", "get_lab_results", "get_medications", "get_clinical_notes"]:
        if "patient_id" not in params:
            raise ActionValidationError(f"Tool '{tool_name}' missing required argument 'patient_id'.")
        validated_params["patient_id"] = validate_patient_id(params["patient_id"])
        
        if tool_name == "get_lab_results" and "test_name" in params and params["test_name"]:
            test_name = str(params["test_name"]).strip()
            if len(test_name) > 50:
                raise ActionValidationError("Parameter 'test_name' exceeds maximum length of 50 chars.")
            validated_params["test_name"] = test_name

    return validated_params
