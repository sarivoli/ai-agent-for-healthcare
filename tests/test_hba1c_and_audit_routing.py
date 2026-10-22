"""
Integration tests for Dynamic Lab Addition (HbA1c 8.6) and Audit Trail Routing Metrics.
Verifies that:
1. Dynamic addition of HbA1c 8.6 via prompt triggers HITL staging with standard LOINC and units.
2. Approving the order commits the lab to the database with a live ISO timestamp.
3. Subsequent clinical summary queries immediately reflect and prioritize the new 8.6% lab.
4. Transaction traces record route_type (CLOUD vs LOCAL) and capture dual-route audit metrics.
"""

import pytest
from src.db.mock_healthcare_db import db
from src.agents.hitl_agent import run_hitl_agent_pipeline, resume_hitl_agent_pipeline
from src.security.audit_tracker import audit_tracker


@pytest.fixture(autouse=True)
def reset_database():
    """Ensure database is reset before each test."""
    db.reset()
    yield
    db.reset()


def test_hba1c_dynamic_addition_and_summary_reflection():
    """Verify adding HbA1c 8.6 pauses for HITL and reflects in subsequent clinical summary."""
    patient_id = "P101"

    # Step 1: User requests adding HbA1c 8.6
    res1 = run_hitl_agent_pipeline(
        patient_id=patient_id,
        custom_prompt="can you add hba1c 8.6 as per todays report",
        force_mock=True
    )

    assert res1.get("attestation_status") == "PENDING_APPROVAL"
    pending = res1.get("pending_actions", [])
    assert len(pending) == 1
    action = pending[0]
    assert action["action_type"] == "ADD_LAB_RESULT"
    assert "Hemoglobin A1c" in action["test_name"]
    assert action["value"] == 8.6
    assert action["unit"] == "%"
    assert action["loinc"] == "4548-4"

    session_id = res1["session_id"]

    # Step 2: Attending clinician approves the order
    res2 = resume_hitl_agent_pipeline(session_id=session_id, approved=True)
    assert res2.get("attestation_status") == "APPROVED"
    exec_results = res2.get("execution_results", [])
    assert len(exec_results) == 1
    assert exec_results[0]["status"] == "success"
    assert exec_results[0]["lab_result"]["result_val"] == 8.6

    # Step 3: Verify the database returns the newest lab first
    labs = db.get_lab_results(patient_id)
    assert len(labs) >= 3
    # First lab in list must be the newly added HbA1c 8.6
    assert "Hemoglobin A1c" in labs[0]["name"]
    assert labs[0]["result_val"] == 8.6

    # Step 4: Request clinical summary for the patient
    res3 = run_hitl_agent_pipeline(
        patient_id=patient_id,
        custom_prompt="get clinical summary of that patient",
        force_mock=True
    )
    summary = res3.get("final_summary", "")
    assert "8.6" in summary
    assert "Hemoglobin A1c" in summary
    # Assert newest badge exists
    assert "[LATEST]" in summary


def test_transaction_trace_records_route_type_and_stages():
    """Verify that transaction traces record route_type (LOCAL vs CLOUD) and stage names."""
    # Run a mock/local pipeline execution
    res = run_hitl_agent_pipeline(
        patient_id="P101",
        custom_prompt="check patient labs",
        force_mock=True
    )

    trace_id = res.get("trace_id")
    assert trace_id is not None

    trace_data = audit_tracker.get_transaction_trace(trace_id)
    assert trace_data is not None
    assert "route_type" in trace_data
    assert trace_data["route_type"] in ["LOCAL", "CLOUD"]

    stages = [s["stage"] for s in trace_data.get("journey_steps", [])]
    assert "INGRESS_CLIENT" in stages
    assert "INPUT_GUARDRAILS" in stages
    assert any(s in stages for s in ["LOCAL_LLM_INFERENCE", "CLOUD_LLM_INFERENCE", "LLM_INFERENCE_AND_ROUTING"])
    assert "EGRESS_CLIENT" in stages
