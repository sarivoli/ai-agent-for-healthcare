"""
FastAPI Streaming Server & REST API for Healthcare Multi-Agent Platform.
Provides endpoints for prompt execution, RBAC authorization, HITL ticket management, and session state retrieval.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.security.rbac import (
    verify_oauth_token,
    is_action_allowed,
    enforce_action_permission,
    apply_field_level_rbac,
    RBACPermissionError
)
from src.agents.session_memory import ticket_manager, HITLTicket
from src.agents.fault_tolerance import fault_tolerant_agent_execute, draft_store
from src.agents.hitl_agent import hitl_agent_app, resume_hitl_agent_pipeline
from src.agents.multi_agent import multi_agent_app
from src.db.mock_healthcare_db import db


app = FastAPI(
    title="Enterprise Healthcare MCP Platform API",
    version="1.0.0",
    description="FastAPI Backend for Dual-LLM PHI Router, Multi-Agent Orchestrator, and Human-in-the-Loop Gates."
)

# CORS middleware for Web UI interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory if present
UI_DIR = Path(__file__).parent.parent / "ui"
if UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")


class ChatRequest(BaseModel):
    prompt: str
    patient_id: str = "P101"
    thread_id: Optional[str] = None
    use_hitl: bool = True


class HITLAttestationRequest(BaseModel):
    ticket_id: str
    clinician_notes: Optional[str] = "Approved by attending physician."


@app.get("/")
def get_root():
    """Serve Web Application dashboard."""
    index_path = UI_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "status": "online",
        "service": "Enterprise Healthcare MCP Platform API",
        "documentation": "/docs"
    }


@app.post("/api/chat")
def process_chat_request(
    req: ChatRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Main Agent execution endpoint.
    Performs OAuth 2.1 token verification, RBAC permission checks, input persistence, and LangGraph workflow invocation.
    """
    auth_claim = verify_oauth_token(authorization or "")
    user_role = auth_claim.get("role", "Clinician")
    thread_id = req.thread_id or f"thread_{user_role.lower()}_101"

    # Enforce basic action permission check for data retrieval
    try:
        enforce_action_permission("get_patient_demographics", user_role)
    except RBACPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    def _execute():
        if req.use_hitl:
            from src.agents.hitl_agent import run_hitl_agent_pipeline
            res = run_hitl_agent_pipeline(
                patient_id=req.patient_id,
                session_id=thread_id,
                role=user_role,
                custom_prompt=req.prompt
            )

            # Check if execution paused at HITL interrupt gate
            if res.get("attestation_status") == "PENDING_APPROVAL":
                pending_actions = res.get("pending_actions", [])
                first_act = pending_actions[0] if pending_actions else {}
                ticket = ticket_manager.create_ticket(
                    thread_id=thread_id,
                    patient_id=req.patient_id,
                    action_type=first_act.get("action_type", "UNKNOWN_ACTION"),
                    action_params=first_act,
                    estimated_eta="15 minutes (Clinician Queue)"
                )
                res["status"] = "AWAITING_CLINICIAN_APPROVAL"
                res["ticket"] = ticket.model_dump()
                res["pending_action"] = {
                    "action_type": first_act.get("action_type", "UNKNOWN_ACTION"),
                    "params": first_act
                }
            
            # Apply field-level RBAC filtering on final output
            return apply_field_level_rbac(res, user_role)
        else:
            # Multi-agent standard pipeline
            initial_state = {
                "patient_id": req.patient_id,
                "user_prompt": req.prompt,
                "next_node": "IngestionAgent"
            }
            res = multi_agent_app.invoke(initial_state)
            return apply_field_level_rbac(res, user_role)

    # Wrap execution in fault tolerance engine
    return fault_tolerant_agent_execute(thread_id, req.prompt, _execute)


@app.get("/api/threads/{thread_id}/status")
def get_thread_status(thread_id: str):
    """Retrieve current thread execution state and associated pending ticket if any."""
    ticket = ticket_manager.get_ticket_by_thread(thread_id)
    draft = draft_store.get_draft(thread_id)
    
    return {
        "thread_id": thread_id,
        "has_pending_ticket": ticket is not None and ticket.status == "AWAITING_CLINICIAN_APPROVAL",
        "ticket": ticket.model_dump() if ticket else None,
        "has_preserved_draft": draft is not None,
        "draft": draft
    }


@app.get("/api/tickets/pending", response_model=List[HITLTicket])
def list_pending_tickets():
    """Retrieve all pending Human-in-the-Loop attestation tickets for clinician review portal."""
    return ticket_manager.get_pending_tickets()


@app.post("/api/hitl/approve")
def approve_ticket(
    req: HITLAttestationRequest,
    authorization: Optional[str] = Header(None)
):
    """Clinician attestation endpoint: Approves pending HITL action and resumes LangGraph workflow."""
    auth_claim = verify_oauth_token(authorization or "")
    user_role = auth_claim.get("role", "Clinician")
    
    try:
        enforce_action_permission("approve_hitl_action", user_role)
    except RBACPermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=f"{str(exc)} Switch your Active Role in the top header to 'Clinician' to approve."
        )

    ticket = ticket_manager.get_ticket_by_id(req.ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket '{req.ticket_id}' not found.")

    if ticket.status != "AWAITING_CLINICIAN_APPROVAL":
        raise HTTPException(status_code=400, detail=f"Ticket '{req.ticket_id}' is already {ticket.status}.")

    ticket_manager.update_ticket_status(req.ticket_id, "APPROVED", req.clinician_notes)
    
    # Resume LangGraph execution pipeline with positive attestation
    final_state = resume_hitl_agent_pipeline(ticket.thread_id, approved=True)
    return {
        "status": "APPROVED",
        "message": f"Ticket {req.ticket_id} approved. Order executed successfully.",
        "ticket": ticket_manager.get_ticket_by_id(req.ticket_id).model_dump(),
        "final_state": final_state
    }


@app.post("/api/hitl/reject")
def reject_ticket(
    req: HITLAttestationRequest,
    authorization: Optional[str] = Header(None)
):
    """Clinician attestation endpoint: Rejects pending HITL action and resumes LangGraph workflow with cancel state."""
    auth_claim = verify_oauth_token(authorization or "")
    user_role = auth_claim.get("role", "Clinician")

    try:
        enforce_action_permission("reject_hitl_action", user_role)
    except RBACPermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=f"{str(exc)} Switch your Active Role in the top header to 'Clinician' to reject."
        )

    ticket = ticket_manager.get_ticket_by_id(req.ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket '{req.ticket_id}' not found.")

    if ticket.status != "AWAITING_CLINICIAN_APPROVAL":
        raise HTTPException(status_code=400, detail=f"Ticket '{req.ticket_id}' is already {ticket.status}.")

    ticket_manager.update_ticket_status(req.ticket_id, "REJECTED", req.clinician_notes)
    
    # Resume LangGraph execution pipeline with rejection
    final_state = resume_hitl_agent_pipeline(ticket.thread_id, approved=False)
    return {
        "status": "REJECTED",
        "message": f"Ticket {req.ticket_id} rejected by clinician. Action cancelled.",
        "ticket": ticket_manager.get_ticket_by_id(req.ticket_id).model_dump(),
        "final_state": final_state
    }
