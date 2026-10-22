"""
Unit and Integration Test Suite for Multi-Lab Staging, Attestation & Execution.
Verifies that when a clinician enters multiple lab results or vitals in a single prompt:
1. All labs are correctly parsed, standardized with LOINC codes, and staged into pending_actions.
2. The HITL ticket holds all staged actions for clinician attestation.
3. Upon approval, all actions are committed to the EHR database.
4. Subsequent clinical summaries dynamically reflect all newly added lab observations.
"""

import pytest
from src.agents.hitl_agent import run_hitl_agent_pipeline, resume_hitl_agent_pipeline
from src.api.server import process_chat_request, approve_ticket, ChatRequest, HITLAttestationRequest
from src.db.mock_healthcare_db import db


@pytest.fixture
def clean_db():
    db.reset()
    return db


def test_multiple_labs_parsed_staged_and_executed(clean_db):
    """
    Test user prompt: 'add following lab reports bp as 140/90 fasting sugar 155 cbc count 140'
    All 3 labs must be staged, attested, and committed to the EHR database.
    """
    patient_id = "P102"
    prompt = "add following lab reports bp as 140/90 fasting sugar 155 cbc count 140"

    # Step 1: Run HITL pipeline
    res1 = run_hitl_agent_pipeline(
        patient_id=patient_id,
        custom_prompt=prompt,
        role="Clinician",
        force_mock=True
    )

    assert res1.get("attestation_status") == "PENDING_APPROVAL"
    pending = res1.get("pending_actions", [])
    assert len(pending) == 3, f"Expected 3 staged actions, got {len(pending)}: {pending}"

    # Verify Blood Pressure action
    bp_act = next((a for a in pending if a["test_name"] == "Blood Pressure"), None)
    assert bp_act is not None
    assert bp_act["value"] == "140/90"
    assert bp_act["systolic"] == 140
    assert bp_act["diastolic"] == 90
    assert bp_act["loinc"] == "85354-9"
    assert bp_act["patient_id"] == "P102"

    # Verify Fasting Sugar action
    sugar_act = next((a for a in pending if "Glucose" in a["test_name"] or "Sugar" in a["test_name"]), None)
    assert sugar_act is not None
    assert sugar_act["value"] == 155.0
    assert sugar_act["unit"] == "mg/dL"
    assert sugar_act["loinc"] == "2345-7"

    # Verify CBC action
    cbc_act = next((a for a in pending if "CBC" in a["test_name"] or "Complete Blood Count" in a["test_name"]), None)
    assert cbc_act is not None
    assert cbc_act["value"] == 140.0
    assert cbc_act["loinc"] == "58410-2"

    # Step 2: Attending clinician approves all orders
    session_id = res1["session_id"]
    res2 = resume_hitl_agent_pipeline(session_id=session_id, approved=True)
    assert res2.get("attestation_status") == "APPROVED"
    exec_results = res2.get("execution_results", [])
    assert len(exec_results) == 3, f"Expected 3 execution results, got {len(exec_results)}"

    # All executions must report success
    for r in exec_results:
        assert r["status"] == "success"

    # Summary table must include all 3 executed rows
    summary = res2.get("final_summary", "")
    assert "Blood Pressure" in summary
    assert "Fasting Blood Glucose" in summary or "Glucose" in summary
    assert "Complete Blood Count" in summary or "CBC" in summary

    # Step 3: Verify EHR database contains all 3 newly added records
    db = clean_db
    labs = db.get_lab_results(patient_id)
    lab_names = [l["name"] for l in labs]
    assert any("Blood Pressure" in n for n in lab_names)
    assert any("Glucose" in n for n in lab_names)
    assert any("Complete Blood Count" in n or "CBC" in n for n in lab_names)

    # Step 4: Verify subsequent clinical summary reflects all 3 observations
    res3 = run_hitl_agent_pipeline(
        patient_id=patient_id,
        custom_prompt="get clinical summary of that patient",
        force_mock=True
    )
    summary_report = res3.get("final_summary", "")
    assert "140/90" in summary_report or "140" in summary_report
    assert "155" in summary_report
    assert "140" in summary_report


def test_api_multi_action_ticket_flow(clean_db):
    """
    Test end-to-end API chat request with multiple labs:
    1. /api/chat returns AWAITING_CLINICIAN_APPROVAL with ticket containing all actions.
    2. /api/hitl/approve commits all orders and returns plural success message.
    """
    req = ChatRequest(
        prompt="add following lab reports bp as 140/90 fasting sugar 155 cbc count 140",
        patient_id="P102",
        use_hitl=True
    )
    auth = "Bearer clinician_token"
    res1 = process_chat_request(req, authorization=auth)

    assert res1.get("status") == "AWAITING_CLINICIAN_APPROVAL"
    assert "pending_actions" in res1
    assert len(res1["pending_actions"]) == 3
    ticket_data = res1.get("ticket", {})
    assert len(ticket_data.get("pending_actions", [])) == 3

    # Approve via API
    ticket_id = ticket_data["ticket_id"]
    attest_req = HITLAttestationRequest(
        ticket_id=ticket_id,
        clinician_notes="Approved all 3 lab observations."
    )
    res2 = approve_ticket(attest_req, authorization=auth)
    assert res2.get("status") == "APPROVED"
    assert "3 clinical orders executed successfully" in res2.get("message", "")
    final_state = res2.get("final_state", {})
    assert len(final_state.get("execution_results", [])) == 3


def test_dual_lab_hba1c_and_cholesterol(clean_db):
    """Verify that entering HbA1c and Cholesterol in a single prompt stages both actions."""
    res = run_hitl_agent_pipeline(
        patient_id="P101",
        custom_prompt="add lab data HbA1c 7.9% and total cholesterol 215 mg/dl",
        role="Clinician",
        force_mock=True
    )
    assert res.get("attestation_status") == "PENDING_APPROVAL"
    pending = res.get("pending_actions", [])
    assert len(pending) == 2
    names = [a["test_name"] for a in pending]
    assert any("HbA1c" in n or "Hemoglobin" in n for n in names)
    assert any("Cholesterol" in n for n in names)

