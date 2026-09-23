"""
Unit & Integration Tests for Module 3: LangGraph Single-Agent Clinical Summarizer.
Verifies tool bindings, ReAct graph execution, persona rendering, and action guardrails.
"""

import json
import pytest
from src.agents.tools import (
    get_patient_demographics,
    get_lab_results,
    get_medications,
    get_clinical_notes
)
from src.agents.prompts import get_persona_prompt, PERSONA_TEMPLATES
from src.agents.single_agent import (
    run_clinical_agent,
    build_single_agent_graph,
    DeterministicClinicalChatModel
)


class TestClinicalTools:
    """Validates that LangChain tool adapters correctly invoke DB and enforce guardrails."""

    def test_get_patient_demographics_valid(self):
        result_raw = get_patient_demographics.invoke({"patient_id": "P101"})
        data = json.loads(result_raw)
        assert data["status"] == "success"
        assert data["data"]["resourceType"] == "Bundle"
        assert data["data"]["id"] == "bundle-P101"

    def test_get_lab_results_valid(self):
        result_raw = get_lab_results.invoke({"patient_id": "P101"})
        data = json.loads(result_raw)
        assert data["status"] == "success"
        assert len(data["labs"]) >= 2
        test_names = [l["name"] for l in data["labs"]]
        assert "Hemoglobin A1c" in test_names

    def test_get_medications_valid(self):
        result_raw = get_medications.invoke({"patient_id": "P101"})
        data = json.loads(result_raw)
        assert data["status"] == "success"
        drugs = [m["drug_name"] for m in data["medications"]]
        assert any("Metformin" in d for d in drugs)

    def test_get_clinical_notes_valid(self):
        result_raw = get_clinical_notes.invoke({"patient_id": "P101"})
        data = json.loads(result_raw)
        assert data["status"] == "success"
        assert len(data["clinical_notes"]) >= 1
        assert "Dr. Sarah Jenkins, MD" in data["clinical_notes"][0]["author"]

    def test_tool_guardrail_rejection(self):
        result_raw = get_patient_demographics.invoke({"patient_id": "P@101#INVALID"})
        data = json.loads(result_raw)
        assert data["status"] == "validation_error"
        assert "Invalid characters" in data["message"]


class TestPersonaPrompts:
    """Validates that persona templates format correctly."""

    def test_physician_prompt_format(self):
        patient_info = {"name": "Eleanor Vance", "mrn": "MRN-884920", "dob": "1965-04-12", "gender": "female"}
        prompt = get_persona_prompt("physician", patient_info)
        assert "CLINICAL SUMMARY (SOAP BRIEF)" in prompt
        assert "Eleanor Vance" in prompt
        assert "MRN-884920" in prompt

    def test_patient_prompt_format(self):
        patient_info = {"name": "Eleanor Vance"}
        prompt = get_persona_prompt("patient", patient_info)
        assert "YOUR PERSONAL HEALTH SUMMARY & CARE PLAN" in prompt
        assert "Hello, Eleanor Vance!" in prompt

    def test_coordinator_prompt_format(self):
        patient_info = {"name": "Eleanor Vance", "mrn": "MRN-884920", "dob": "1965-04-12"}
        prompt = get_persona_prompt("coordinator", patient_info)
        assert "CARE COORDINATOR QUALITY & GAP AUDIT" in prompt


class TestSingleAgentExecution:
    """Tests full end-to-end LangGraph ReAct workflow."""

    def test_graph_compilation(self):
        mock_llm = DeterministicClinicalChatModel()
        graph = build_single_agent_graph(mock_llm)
        assert graph is not None

    def test_physician_soap_synthesis(self):
        result = run_clinical_agent(patient_id="P101", persona="physician", force_mock=True)
        assert "final_summary" in result
        summary = result["final_summary"]
        assert "CLINICAL SUMMARY (SOAP BRIEF)" in summary
        assert "Eleanor Vance" in summary
        assert "MRN-884920" in summary
        assert "Hemoglobin A1c" in summary

    def test_patient_discharge_synthesis(self):
        result = run_clinical_agent(patient_id="P101", persona="patient", force_mock=True)
        summary = result.get("final_summary", "")
        assert "YOUR PERSONAL HEALTH SUMMARY & CARE PLAN" in summary
        assert "Eleanor Vance" in summary
        assert "Metformin" in summary

    def test_coordinator_audit_synthesis(self):
        result = run_clinical_agent(patient_id="P101", persona="coordinator", force_mock=True)
        summary = result.get("final_summary", "")
        assert "CARE COORDINATOR QUALITY & GAP AUDIT" in summary
        assert "Eleanor Vance" in summary
        assert "HEDIS" in summary
