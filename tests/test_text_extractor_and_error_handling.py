"""
Unit Tests for Text Normalization, Raw LLM Payload Extraction, and System-Wide Error Logging.
Verifies that:
1. List of parts/chunks from ChatGoogleGenerativeAI (Gemini) are unpacked into clean text.
2. Serialized Python repr strings of dict lists are cleanly decoded.
3. Base64 signature envelopes are stripped.
4. Execution exceptions trigger graceful fallback responses with prompt preservation and audit incident logging.
5. RBAC permission errors return informative clinician messages and log audit events.
"""

import pytest
from src.utils.text_extractor import extract_message_text
from src.agents.fault_tolerance import fault_tolerant_agent_execute, draft_store
from src.security.audit_tracker import audit_tracker
from fastapi.testclient import TestClient
from src.api.server import app


def test_extract_message_text_from_plain_string():
    raw = "Here is a standard clinical summary for Eleanor Vance."
    assert extract_message_text(raw) == raw


def test_extract_message_text_from_list_of_dict_chunks():
    # Simulates Gemini 3.6 Flash text chunk stream
    chunks = [
        {"type": "text", "text": "Here is the summary for P101.\n\n| Test"},
        {"type": "text", "text": " Name | Result |\n| HbA1c | 8.4% |"},
        {"extras": {"signature": "base64_crypto_signature_xyz"}}
    ]
    extracted = extract_message_text(chunks)
    assert "| Test Name | Result |" in extracted
    assert "| HbA1c | 8.4% |" in extracted
    assert "signature" not in extracted


def test_extract_message_text_from_serialized_python_list():
    # Simulates when a list of dicts was inadvertently stringified via str()
    repr_str = "[{'type': 'text', 'text': 'Demographics: Female 61'}, {'type': 'text', 'text': ' years old.'}]"
    extracted = extract_message_text(repr_str)
    assert extracted == "Demographics: Female 61 years old."


def test_fault_tolerant_agent_execute_incident_logging():
    thread_id = "test_thread_err_audit_01"
    prompt = "Prescribe Experimental Drug 100mg"

    def _broken_fn():
        raise RuntimeError("Simulated Database Timeout")

    res = fault_tolerant_agent_execute(thread_id, prompt, _broken_fn)

    assert res["status"] == "agent_error"
    assert res["incident_id"].startswith("INC-")
    assert "Simulated Database Timeout" in res["error_message"]
    assert res["user_input_preserved"] is True
    assert res["draft_prompt"] == prompt
    assert "audit team has logged this incident" in res["user_message"]


def test_fastapi_audit_incidents_endpoint():
    client = TestClient(app)
    resp = client.get("/api/audit/incidents")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_incidents" in data
    assert "incidents" in data
    assert isinstance(data["incidents"], list)


def test_fastapi_rbac_denial_graceful_response():
    client = TestClient(app)
    # Analyst role trying to approve HITL ticket
    resp = client.post(
        "/api/hitl/approve",
        json={"ticket_id": "TICKET-999", "clinician_notes": "Attempt by analyst"},
        headers={"Authorization": "Bearer analyst_token"}
    )
    assert resp.status_code == 403
    data = resp.json()
    assert "detail" in data
    assert "Clinician" in data["detail"]
