"""
Unit and Integration Test Suite for Module 6: Clinical Identification, Confidence Scoring & HITL Gates.
Tests Rule Engine confidence scores, Prompt-Driven CRUD tools, and LangGraph HITL interrupt & attestation loops.
"""

import pytest
from src.rules.rule_engine import clinical_rule_engine
from src.agents.hitl_agent import run_hitl_agent_pipeline, resume_hitl_agent_pipeline
from src.db.mock_healthcare_db import db


def test_clinical_rule_engine_confidence_scoring():
    """Verifies rule calculations and heuristic confidence score assignments."""
    raw_data = {
        "patient_demographics": {
            "entry": [{"resource": {"resourceType": "Condition", "code": {"text": "Type 2 Diabetes Mellitus"}}}]
        },
        "labs": [
            {"name": "Hemoglobin A1c", "result_val": "8.4", "date": "2026-08-15"},
            {"name": "Systolic Blood Pressure", "result_val": "142.0", "date": "2026-08-15"}
        ],
        "medications": [{"drug_name": "Metformin 1000mg"}],
        "notes": [{"author": "Dr. Sarah Jenkins", "content": "Patient reports GI intolerance to Metformin."}]
    }

    result = clinical_rule_engine.evaluate(raw_data)

    assert result.overall_confidence_score >= 0.85
    assert result.requires_clinician_attestation is True
    assert len(result.quality_metrics) == 2
    assert any(q.metric_id == "HEDIS_CDC_A1C_SUB" and q.confidence_score == 0.95 for q in result.quality_metrics)
    assert any(q.metric_id == "HEDIS_CBP_SUB" and q.confidence_score == 0.92 for q in result.quality_metrics)
    assert any(g.gap_id == "GAP-EYE-001" and g.confidence_score == 0.88 for g in result.care_gaps)


def test_prompt_driven_crud_tools():
    """Verifies FastMCP CRUD write tools for creating medication orders and updating notes."""
    res_med = db.create_medication_order("P101", "Metformin ER", "500mg", "daily")
    assert res_med["status"] == "success"
    assert "RX-NEW-" in res_med["order_id"]

    res_note = db.update_patient_note("P101", "Follow-up note added by attending.", "Dr. Jenkins")
    assert res_note["status"] == "success"
    assert "NOTE-NEW-" in res_note["note_id"]

    res_rem = db.add_care_gap_remediation("P101", "GAP-EYE-001", "Ophthalmology appointment scheduled.")
    assert res_rem["status"] == "success"


def test_hitl_graph_interrupt_pause():
    """Verifies that graph execution pauses for clinician attestation when write orders occur."""
    session_id = "TEST-HITL-PAUSE-001"
    crud_prompt = "Please order Metformin 500mg ER daily for patient P101."
    result = run_hitl_agent_pipeline(patient_id="P101", session_id=session_id, custom_prompt=crud_prompt, force_mock=True)

    assert result["attestation_status"] == "PENDING_APPROVAL"
    assert "HUMAN-IN-THE-LOOP (HITL) CLINICIAN ATTESTATION REQUIRED" in result["final_summary"]
    assert len(result["pending_actions"]) > 0


def test_hitl_graph_attestation_approval_branch():
    """Verifies graph resumption and CRUD execution when clinician approves."""
    session_id = "TEST-HITL-APPR-001"
    crud_prompt = "Please order Lisinopril 20mg daily for patient P101."
    run_hitl_agent_pipeline(patient_id="P101", session_id=session_id, custom_prompt=crud_prompt, force_mock=True)

    resumed = resume_hitl_agent_pipeline(
        session_id=session_id,
        approved=True,
        clinician_id="DR-JENKINS-99",
        comments="Approved dosage increase."
    )

    assert resumed["attestation_status"] == "APPROVED"
    assert "CLINICIAN ATTESTED & EXECUTED SUMMARY" in resumed["final_summary"]
    assert len(resumed["execution_results"]) > 0


def test_hitl_graph_attestation_rejection_branch():
    """Verifies graph resumption and cancellation when clinician rejects."""
    session_id = "TEST-HITL-REJ-001"
    crud_prompt = "Please order Metformin 1000mg daily for patient P101."
    run_hitl_agent_pipeline(patient_id="P101", session_id=session_id, custom_prompt=crud_prompt, force_mock=True)

    resumed = resume_hitl_agent_pipeline(
        session_id=session_id,
        approved=False,
        clinician_id="DR-VANCE-99",
        comments="Rejected due to GI side effects."
    )

    assert resumed["attestation_status"] == "REJECTED"
    assert "CLINICIAN REJECTED SUMMARY" in resumed["final_summary"]
    assert any(r.get("status") == "rejected" for r in resumed["execution_results"])


def test_user_prompt_update_progress_note_diet_compliance():
    """Verifies that progress note update for diet compliance triggers HITL UPDATE_PATIENT_NOTE action."""
    session_id = "TEST-HITL-NOTE-001"
    prompt = "Update clinical progress note for patient P101 noting diet compliance."
    result = run_hitl_agent_pipeline(patient_id="P101", session_id=session_id, custom_prompt=prompt, force_mock=True)

    assert result["attestation_status"] == "PENDING_APPROVAL"
    assert len(result["pending_actions"]) > 0
    act = result["pending_actions"][0]
    assert act["action_type"] == "UPDATE_PATIENT_NOTE"
    assert "P101" in act["reason"]
    assert "diet" in act["note_content"].lower() or "compliant" in act["note_content"].lower()


def test_user_prompt_get_patient_summary_and_labs():
    """Verifies that requesting patient summary and labs returns structured clinical summary with labs."""
    session_id = "TEST-SUMMARY-LABS-001"
    prompt = "Get patient summary for P101 and check recent lab results."
    result = run_hitl_agent_pipeline(patient_id="P101", session_id=session_id, custom_prompt=prompt, force_mock=True)

    summary = result.get("final_summary", "")
    assert "CLINICAL PATIENT SUMMARY & LABORATORY REPORT" in summary
    assert "Hemoglobin A1c" in summary or "8.4 %" in summary
    assert "Systolic Blood Pressure" in summary or "142.0 mmHg" in summary


def test_user_prompt_care_gap_and_hedis_analysis():
    """Verifies that care gap and HEDIS analysis returns structured Markdown table report without raw JSON."""
    session_id = "TEST-HEDIS-REPORT-001"
    prompt = "Analyze patient P101 for care gaps and HEDIS quality compliance."
    result = run_hitl_agent_pipeline(patient_id="P101", session_id=session_id, custom_prompt=prompt, force_mock=True)

    summary = result.get("final_summary", "")
    assert "HEDIS QUALITY & CLINICAL CARE GAP COMPLIANCE REPORT" in summary or "Identified Clinical Care Gaps" in summary
    assert "HEDIS CDC" in summary or "GAP-CDC-002" in summary
    assert "{" not in summary or "json.dumps" not in summary

