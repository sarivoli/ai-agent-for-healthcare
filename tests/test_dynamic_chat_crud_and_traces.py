"""
Unit & Integration Tests for Dynamic Chat CRUD Operations and Dedicated Transaction Journey Audit Logger.
Validates:
- Dynamic parsing & HITL staging of medications, lab results, and clinical notes from chat prompts
- Clinician attestation & execution in EHR database
- Dedicated transaction journey audit trace recording in JSON and append-only audit log
- API endpoints for audit traces retrieval
"""

import pytest
from src.db.mock_healthcare_db import db
from src.agents.hitl_agent import run_hitl_agent_pipeline, resume_hitl_agent_pipeline
from src.security.audit_tracker import audit_tracker
from fastapi.testclient import TestClient
from src.api.server import app


@pytest.fixture(autouse=True)
def reset_db_state():
    """Reset mock database before each test."""
    db.reset()


def test_dynamic_medication_order_via_chat():
    """Verifies user can order medication dynamically via chat conversation."""
    session_id = "test_sess_med_01"
    prompt = "Patient has elevated HbA1c. Prescribe Metformin 500mg daily"
    
    # 1. Run pipeline - should detect action and pause at HITL gate
    res = run_hitl_agent_pipeline(
        patient_id="P101",
        session_id=session_id,
        role="Clinician",
        custom_prompt=prompt,
        force_mock=True
    )
    
    assert res.get("attestation_status") == "PENDING_APPROVAL"
    assert len(res.get("pending_actions", [])) == 1
    act = res["pending_actions"][0]
    assert act["action_type"] == "CREATE_MEDICATION_ORDER"
    assert "Metformin" in act["drug_name"]
    assert "500mg" in act["dosage"]
    assert "trace_id" in res
    
    # 2. Clinician attestation approval
    res_approved = resume_hitl_agent_pipeline(
        session_id=session_id,
        approved=True,
        clinician_id="DR-TEST-01",
        comments="Approved medication adjustment."
    )
    
    assert res_approved.get("attestation_status") == "APPROVED"
    assert len(res_approved.get("execution_results", [])) == 1
    exec_res = res_approved["execution_results"][0]
    assert exec_res["status"] == "success"
    assert "order_id" in exec_res
    
    # Verify EHR DB has updated prescriptions
    meds = db.get_medications("P101")
    assert any("Metformin 500mg" in m.get("drug_name", "") for m in meds)


def test_dynamic_lab_result_entry_via_chat():
    """Verifies clinician can add new lab result dynamically via chat conversation."""
    session_id = "test_sess_lab_01"
    prompt = "Add lab result HbA1c 7.1% for patient P101"
    
    res = run_hitl_agent_pipeline(
        patient_id="P101",
        session_id=session_id,
        role="Clinician",
        custom_prompt=prompt,
        force_mock=True
    )
    
    assert res.get("attestation_status") == "PENDING_APPROVAL"
    assert len(res.get("pending_actions", [])) == 1
    act = res["pending_actions"][0]
    assert act["action_type"] == "ADD_LAB_RESULT"
    assert "HbA1c" in act["test_name"]
    assert float(act["value"]) == 7.1
    assert act["unit"] == "%"
    
    # Approve and commit
    res_approved = resume_hitl_agent_pipeline(
        session_id=session_id,
        approved=True,
        clinician_id="DR-TEST-01",
        comments="Verified lab report from pathology."
    )
    
    assert res_approved.get("attestation_status") == "APPROVED"
    labs = db.get_lab_results("P101")
    assert any(l.get("result_val") == 7.1 and "HbA1c" in l.get("name", "") for l in labs)


def test_dynamic_clinical_note_entry_via_chat():
    """Verifies clinician can add a clinical progress note dynamically via chat conversation."""
    session_id = "test_sess_note_01"
    prompt = "Add clinical note for patient P101: Patient attended diabetic foot exam with normal findings"
    
    res = run_hitl_agent_pipeline(
        patient_id="P101",
        session_id=session_id,
        role="Clinician",
        custom_prompt=prompt,
        force_mock=True
    )
    
    assert res.get("attestation_status") == "PENDING_APPROVAL"
    assert len(res.get("pending_actions", [])) == 1
    act = res["pending_actions"][0]
    assert act["action_type"] == "UPDATE_PATIENT_NOTE"
    assert "diabetic foot exam" in act["note_content"]
    
    # Approve and commit
    res_approved = resume_hitl_agent_pipeline(
        session_id=session_id,
        approved=True,
        clinician_id="DR-TEST-01",
        comments="Attested progress note."
    )
    
    assert res_approved.get("attestation_status") == "APPROVED"
    notes = db.get_clinical_notes("P101")
    assert any("diabetic foot exam" in n.get("content", "") for n in notes)


def test_transaction_journey_audit_logger():
    """Verifies the dedicated transaction journey logger records trace files and audit log entries."""
    session_id = "test_sess_audit_journey_01"
    prompt = "Add lab result Potassium 4.8 mEq/L for patient P101"
    
    res = run_hitl_agent_pipeline(
        patient_id="P101",
        session_id=session_id,
        role="Clinician",
        custom_prompt=prompt,
        force_mock=True
    )
    
    trace_id = res.get("trace_id")
    assert trace_id is not None
    assert trace_id.startswith("TRX-")
    
    # Check trace retrieval via audit tracker
    trace_data = audit_tracker.get_transaction_trace(trace_id)
    assert trace_data is not None
    assert trace_data["trace_id"] == trace_id
    assert trace_data["patient_id"] == "P101"
    assert trace_data["prompt"] == prompt
    assert len(trace_data["journey_steps"]) >= 3
    
    # Check that audit_journey.log file exists and contains the trace
    traces_dir = audit_tracker.reports_dir.parent / "transaction_traces"
    log_file = traces_dir / "audit_journey.log"
    assert log_file.exists()
    with open(log_file, "r", encoding="utf-8") as f:
        log_content = f.read()
    assert trace_id in log_content


def test_api_audit_traces_endpoints():
    """Verifies FastAPI endpoints for listing and viewing transaction traces."""
    client = TestClient(app)
    
    # 1. Trigger a chat request via API
    chat_resp = client.post(
        "/api/chat",
        json={
            "prompt": "Add lab result HbA1c 6.9% for patient P101",
            "patient_id": "P101",
            "thread_id": "test_thread_api_traces_01"
        },
        headers={"Authorization": "Bearer mock_token"}
    )
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert "ticket" in chat_data or "pending_action" in chat_data
    
    # 2. List traces endpoint
    traces_resp = client.get("/api/audit/traces")
    assert traces_resp.status_code == 200
    traces_list = traces_resp.json()
    assert "traces" in traces_list
    assert len(traces_list["traces"]) > 0
    
    # 3. Retrieve specific trace
    sample_tid = traces_list["traces"][0]["trace_id"]
    single_resp = client.get(f"/api/audit/traces/{sample_tid}")
    assert single_resp.status_code == 200
    assert single_resp.json()["trace_id"] == sample_tid
    
    # 4. Journey log endpoint
    log_resp = client.get("/api/audit/journey-log")
    assert log_resp.status_code == 200
    assert "log" in log_resp.json()


def test_dynamic_bp_vital_entry_and_summary_persistence():
    """
    Verifies clinician can add blood pressure (e.g. 'add current bp as 140/90'),
    stage it via HITL gate, commit it to DB upon approval, and verify it appears
    in subsequent clinical summaries.
    """
    session_id = "test_sess_bp_vital_01"
    prompt = "add current bp as 140/90"

    # 1. Run pipeline - should parse BP as staged ADD_LAB_RESULT action
    res = run_hitl_agent_pipeline(
        patient_id="P101",
        session_id=session_id,
        role="Clinician",
        custom_prompt=prompt,
        force_mock=True
    )

    assert res.get("attestation_status") == "PENDING_APPROVAL"
    assert len(res.get("pending_actions", [])) == 1
    act = res["pending_actions"][0]
    assert act["action_type"] == "ADD_LAB_RESULT"
    assert "Blood Pressure" in act["test_name"] or "BP" in act["test_name"]
    assert act.get("systolic") == 140
    assert act.get("diastolic") == 90
    assert act.get("value") == "140/90"

    # 2. Clinician attests and approves
    res_approved = resume_hitl_agent_pipeline(
        session_id=session_id,
        approved=True,
        clinician_id="DR-CARTER-01",
        comments="Attested current clinic BP reading."
    )

    assert res_approved.get("attestation_status") == "APPROVED"
    assert len(res_approved.get("execution_results", [])) >= 1

    # 3. Verify Mock Healthcare Database has recorded the observation
    labs = db.get_lab_results("P101")
    assert any("Blood Pressure" in l.get("name", "") or l.get("result_val") == 140.0 for l in labs)

    # 4. Verify pulling clinical summary retrieves the newly added BP
    summary_res = run_hitl_agent_pipeline(
        patient_id="P101",
        session_id="test_sess_bp_summary_check",
        role="Clinician",
        custom_prompt="Get patient summary for P101 and check recent lab results.",
        force_mock=True
    )

    summary_text = summary_res.get("final_summary", "")
    assert "140" in summary_text or "Blood Pressure" in summary_text


def test_llm_telemetry_in_audit_trace():
    """
    Verifies that transaction traces capture LLM connection endpoint, model,
    prompt tokens, completion tokens, call total, and accumulated session quota.
    """
    session_id = "test_sess_telemetry_01"
    prompt = "Get patient summary for P101"

    res = run_hitl_agent_pipeline(
        patient_id="P101",
        session_id=session_id,
        role="Clinician",
        custom_prompt=prompt,
        force_mock=True
    )

    trace_id = res.get("trace_id")
    assert trace_id is not None
    trace_data = audit_tracker.get_transaction_trace(trace_id)
    assert trace_data is not None

    # Check LLM Inference & Routing milestone step
    step_stages = [s["stage"] for s in trace_data["journey_steps"]]
    assert "PHI_SCAN_AND_DEID" in step_stages
    assert "LLM_INFERENCE_AND_ROUTING" in step_stages

    llm_step = next(s for s in trace_data["journey_steps"] if s["stage"] == "LLM_INFERENCE_AND_ROUTING")
    details = llm_step["details"]
    assert "provider" in details
    assert "model" in details
    assert "endpoint" in details
    assert details["prompt_tokens"] > 0
    assert details["total_call_tokens"] > 0
    assert "session_tokens_used_so_far" in details
    assert "session_remaining_quota" in details
    assert details["session_quota_limit"] == 8000


def test_traces_sorted_newest_first():
    """Verifies list_transaction_traces always returns the newest traces first."""
    trace_ids = audit_tracker.list_transaction_traces()
    assert len(trace_ids) >= 2
    # Verify first trace exists and was modified at or after subsequent ones
    traces_dir = audit_tracker.reports_dir.parent / "transaction_traces"
    first_file = traces_dir / f"{trace_ids[0]}.json"
    second_file = traces_dir / f"{trace_ids[1]}.json"
    assert first_file.stat().st_mtime >= second_file.stat().st_mtime

