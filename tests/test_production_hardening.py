"""
Module 7 Unit Test Suite: Production Hardening, RBAC, Session Memory & Web API
Run with: python -m pytest tests/test_production_hardening.py
"""

import pytest
from src.security.rbac import verify_oauth_token, is_action_allowed, apply_field_level_rbac, RBACPermissionError, enforce_action_permission
from src.agents.session_memory import ticket_manager
from src.agents.fault_tolerance import fault_tolerant_agent_execute, draft_store
from src.api.server import process_chat_request, approve_ticket, reject_ticket, list_pending_tickets, ChatRequest, HITLAttestationRequest


def test_rbac_token_decoding_roles():
    clinician = verify_oauth_token("Bearer clinician_token")
    analyst = verify_oauth_token("Bearer analyst_token")
    auditor = verify_oauth_token("Bearer auditor_token")

    assert clinician["role"] == "Clinician"
    assert analyst["role"] == "Analyst"
    assert auditor["role"] == "Auditor"


def test_rbac_action_permissions():
    assert is_action_allowed("create_medication_order", "Clinician") is True
    assert is_action_allowed("create_medication_order", "Analyst") is False

    with pytest.raises(RBACPermissionError):
        enforce_action_permission("create_medication_order", "Analyst")


def test_field_level_rbac_redaction():
    sample_payload = {
        "data": {"id": "bundle-P101", "name": "Eleonora Vance"},
        "clinical_notes": [{"note_id": "NOTE-101", "author": "Dr. Sarah Jenkins"}]
    }

    analyst_filtered = apply_field_level_rbac(sample_payload, "Analyst")
    assert analyst_filtered["clinical_notes"][0]["author"] == "[REDACTED_FOR_ANALYST]"

    auditor_filtered = apply_field_level_rbac(sample_payload, "Auditor")
    assert auditor_filtered["data"]["name"] == "[REDACTED_BY_AUDITOR_RBAC]"


def test_ticket_manager_lifecycle():
    ticket = ticket_manager.create_ticket(
        thread_id="thread_test_101",
        patient_id="P101",
        action_type="create_medication_order",
        action_params={"drug_name": "Lisinopril 20mg"}
    )

    assert ticket.ticket_id.startswith("HITL-")
    assert ticket.status == "AWAITING_CLINICIAN_APPROVAL"

    updated = ticket_manager.update_ticket_status(ticket.ticket_id, "APPROVED", "Approved by physician.")
    assert updated.status == "APPROVED"
    assert updated.clinician_notes == "Approved by physician."


def test_fault_tolerant_input_preservation():
    def _failing_fn():
        raise ValueError("Database write failed")

    res = fault_tolerant_agent_execute(
        thread_id="thread_fail_999",
        prompt="Order Insulin 10 units",
        execution_fn=_failing_fn
    )

    assert res["status"] == "agent_error"
    assert res["user_input_preserved"] is True
    assert res["draft_prompt"] == "Order Insulin 10 units"


def test_fastapi_chat_and_attestation_flow():
    req = ChatRequest(
        prompt="Prescribe Metformin 500mg for patient P101",
        patient_id="P101",
        thread_id="thread_api_test_55",
        use_hitl=True
    )

    chat_res = process_chat_request(req, authorization="Bearer clinician_token")
    assert chat_res["status"] == "AWAITING_CLINICIAN_APPROVAL"
    ticket_id = chat_res["ticket"]["ticket_id"]

    # Approve ticket via API
    attest_req = HITLAttestationRequest(ticket_id=ticket_id, clinician_notes="Verified.")
    attest_res = approve_ticket(attest_req, authorization="Bearer clinician_token")

    assert attest_res["status"] == "APPROVED"
    assert attest_res["final_state"]["attestation_status"] == "APPROVED"

