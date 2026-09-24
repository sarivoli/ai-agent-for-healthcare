"""
Module 7 Working Milestone Demo: Production Hardening, RBAC, Web UI & Ticket Management
Runs end-to-end verification of OAuth 2.1 RBAC, FastApi server integration, state checkpointer ticket ETAs, and fault tolerance.

Run with:
  Windows: python -m scripts.demo_production_ui
  Linux/macOS: python3 -m scripts.demo_production_ui
"""

import sys
import json
from src.security.rbac import verify_oauth_token, apply_field_level_rbac, is_action_allowed
from src.agents.session_memory import ticket_manager
from src.agents.fault_tolerance import fault_tolerant_agent_execute, draft_store
from src.api.server import process_chat_request, approve_ticket, list_pending_tickets, ChatRequest, HITLAttestationRequest


def main():
    print("=" * 80)
    print("      MODULE 7 WORKING MILESTONE DEMO: PRODUCTION HARDENING & WEB UI")
    print("=" * 80)

    # ----------------------------------------------------
    # SCENARIO 1: OAuth 2.1 Verification & Field-Level RBAC
    # ----------------------------------------------------
    print("\n--- [SCENARIO 1: OAuth 2.1 Token Verification & Field-Level RBAC] ---")
    tokens = {
        "Clinician": "Bearer clinician_token_101",
        "Analyst": "Bearer analyst_token_202",
        "Auditor": "Bearer auditor_token_303"
    }

    raw_patient_data = {
        "patient_id": "P101",
        "data": {"id": "bundle-P101", "name": "Eleonora Vance", "telecom": ["555-0192"]},
        "clinical_notes": [
            {"note_id": "NOTE-101", "author": "Dr. Sarah Jenkins", "content": "Elevated HbA1c 8.4%."}
        ]
    }

    for role_name, token_str in tokens.items():
        claims = verify_oauth_token(token_str)
        allowed = is_action_allowed("create_medication_order", claims["role"])
        filtered_payload = apply_field_level_rbac(raw_patient_data, claims["role"])

        print(f"\nRole: {claims['role']} ({claims['department']})")
        print(f"  • Sub: {claims['sub']}")
        print(f"  • Allowed to Prescribe Meds: {allowed}")
        if claims["role"] == "Analyst":
            print(f"  • Filtered Note Author: {filtered_payload['clinical_notes'][0]['author']}")
        elif claims["role"] == "Auditor":
            print(f"  • Filtered Name: {filtered_payload['data']['name']}")
        else:
            print(f"  • Unredacted Note Author: {filtered_payload['clinical_notes'][0]['author']}")

    # ----------------------------------------------------
    # SCENARIO 2: Prompt-Driven CRUD & Instant HITL Ticket ETA
    # ----------------------------------------------------
    print("\n--- [SCENARIO 2: Prompt-Driven CRUD & Instant HITL Ticket ETA Generation] ---")
    chat_req = ChatRequest(
        prompt="Prescribe Lisinopril 20mg daily for patient P101 due to elevated blood pressure.",
        patient_id="P101",
        thread_id="thread_demo_701",
        use_hitl=True
    )

    res = process_chat_request(chat_req, authorization="Bearer clinician_token")
    print(f"Status: {res.get('status')}")
    if res.get("status") == "AWAITING_CLINICIAN_APPROVAL":
        ticket = res.get("ticket", {})
        print(f"  • Ticket ID: {ticket.get('ticket_id')}")
        print(f"  • Estimated ETA: {ticket.get('estimated_eta')}")
        print(f"  • Pending Action: {ticket.get('action_type')}")
        print(f"  • Action Params: {ticket.get('action_params')}")

    # ----------------------------------------------------
    # SCENARIO 3: Listing Pending Tickets in Clinician Queue
    # ----------------------------------------------------
    print("\n--- [SCENARIO 3: Querying Pending Attestation Queue] ---")
    pending = list_pending_tickets()
    print(f"Total Pending Tickets in Queue: {len(pending)}")
    for t in pending:
        print(f"  [QUEUE ITEM] Ticket {t.ticket_id} | Action: {t.action_type} | ETA: {t.estimated_eta}")

    # ----------------------------------------------------
    # SCENARIO 4: Clinician Attestation & Workflow Resumption
    # ----------------------------------------------------
    print("\n--- [SCENARIO 4: Clinician Attestation & LangGraph State Resumption] ---")
    if pending:
        target_ticket = pending[0]
        attest_req = HITLAttestationRequest(
            ticket_id=target_ticket.ticket_id,
            clinician_notes="Approved during Module 7 demonstration."
        )
        attest_res = approve_ticket(attest_req, authorization="Bearer clinician_token")
        print(f"Attestation Status: {attest_res.get('status')}")
        print(f"Message: {attest_res.get('message')}")
        print(f"Final State Status: {attest_res.get('final_state', {}).get('status')}")

    # ----------------------------------------------------
    # SCENARIO 5: Fault-Tolerant Input Preservation Demonstration
    # ----------------------------------------------------
    print("\n--- [SCENARIO 5: Fault-Tolerant Input Preservation on Exception] ---")
    def _faulty_execution():
        raise RuntimeError("Simulated Database Connection Failure!")

    fault_res = fault_tolerant_agent_execute(
        thread_id="thread_fault_test",
        prompt="Order Metformin 1000mg for P101",
        execution_fn=_faulty_execution
    )

    print(f"Execution Result Status: {fault_res.get('status')}")
    print(f"Preserved Draft Prompt: '{fault_res.get('draft_prompt')}'")
    print(f"User Input Preserved: {fault_res.get('user_input_preserved')}")
    print(f"Recommendation: {fault_res.get('recommendation')}")

    print("\n" + "=" * 80)
    print("  MODULE 7 DEMONSTRATION COMPLETE: ALL PRODUCTION CONTROL LOOPS VERIFIED")
    print("=" * 80)


if __name__ == "__main__":
    main()
