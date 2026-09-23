"""
Module 2 Unit Test Suite: FastMCP Server & Action Validation
Run with: python -m pytest tests/test_mcp_server.py
"""

import json
from src.mcp_server.server import get_patient_demographics, get_lab_results, get_medications, get_clinical_notes
from src.security.action_validator import validate_patient_id, ActionValidationError


def test_mcp_server_demographics_valid():
    res_str = get_patient_demographics("P101")
    data = json.loads(res_str)
    assert data["status"] == "success"
    assert data["data"]["id"] == "bundle-P101"


def test_mcp_server_labs_valid():
    res_str = get_lab_results("P101")
    data = json.loads(res_str)
    assert data["status"] == "success"
    assert len(data["labs"]) == 2


def test_mcp_server_medications_valid():
    res_str = get_medications("P101")
    data = json.loads(res_str)
    assert data["status"] == "success"
    assert len(data["medications"]) == 2


def test_mcp_server_clinical_notes_valid():
    res_str = get_clinical_notes("P101")
    data = json.loads(res_str)
    assert data["status"] == "success"
    assert len(data["clinical_notes"]) == 1


def test_action_guardrail_invalid_patient_id():
    res_str = get_patient_demographics("P!01<INVALID>")
    data = json.loads(res_str)
    assert data["status"] == "validation_error"
    assert "Invalid characters" in data["message"]
