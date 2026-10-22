"""
FastAPI Streaming Server & REST API for Healthcare Multi-Agent Platform.
Provides endpoints for prompt execution, RBAC authorization, HITL ticket management, and session state retrieval.
"""

import os
import json
import time
import uuid
import traceback
from typing import Dict, Any, Optional, List
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
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
from src.security.audit_tracker import audit_tracker
from src.utils.text_extractor import extract_message_text


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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler capturing unexpected server/agent errors into audit log."""
    incident_id = f"INC-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}"
    err_stack = traceback.format_exc()
    audit_tracker.log_event("SYSTEM_API_EXCEPTION", {
        "incident_id": incident_id,
        "url": str(request.url),
        "method": request.method,
        "error": str(exc),
        "error_type": type(exc).__name__,
        "traceback": err_stack[:500]
    })
    return JSONResponse(
        status_code=500,
        content={
            "status": "system_error",
            "incident_id": incident_id,
            "error_type": type(exc).__name__,
            "error_message": f"Healthcare Platform Service Notice: {str(exc)}",
            "user_message": (
                "An unexpected condition occurred while processing your request. "
                f"The clinical system has recorded this incident under ticket Reference '{incident_id}' for audit review."
            ),
            "recommendation": "Your request has been safely captured in system logs. You may retry or contact clinical system administration."
        }
    )


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


@app.get("/audit")
def get_audit_page():
    """Serve Dedicated Transaction Journey Audit Explorer."""
    audit_path = UI_DIR / "audit.html"
    if audit_path.exists():
        return FileResponse(str(audit_path))
    return {
        "status": "error",
        "message": "Audit page not found."
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

    # Reconcile effective patient ID if prompt explicitly specifies a target patient ID
    import re
    match_pid = re.search(r"\b(P10[1-9])\b", req.prompt, re.IGNORECASE)
    effective_patient_id = match_pid.group(1).upper() if match_pid else req.patient_id

    # Enforce basic action permission check for data retrieval
    try:
        enforce_action_permission("get_patient_demographics", user_role)
    except RBACPermissionError as exc:
        incident_id = f"INC-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}"
        audit_tracker.log_event("RBAC_PERMISSION_DENIED", {
            "incident_id": incident_id,
            "role": user_role,
            "action": "get_patient_demographics",
            "thread_id": thread_id,
            "prompt": req.prompt,
            "error": str(exc)
        })
        raise HTTPException(
            status_code=403,
            detail=f"{str(exc)} Switch your Active Role in the top header to 'Clinician' to proceed."
        )

    def _execute():
        if req.use_hitl:
            from src.agents.hitl_agent import run_hitl_agent_pipeline
            res = run_hitl_agent_pipeline(
                patient_id=effective_patient_id,
                session_id=thread_id,
                role=user_role,
                custom_prompt=req.prompt
            )

            # Check if execution paused at HITL interrupt gate
            if res.get("attestation_status") == "PENDING_APPROVAL":
                pending_actions = res.get("pending_actions", [])
                first_act = pending_actions[0] if pending_actions else {}
                action_type_label = (
                    first_act.get("action_type", "UNKNOWN_ACTION")
                    if len(pending_actions) <= 1
                    else f"MULTIPLE_ACTIONS ({len(pending_actions)} items)"
                )
                ticket = ticket_manager.create_ticket(
                    thread_id=thread_id,
                    patient_id=effective_patient_id,
                    action_type=action_type_label,
                    action_params=first_act,
                    pending_actions=pending_actions,
                    estimated_eta="15 minutes (Clinician Queue)"
                )
                res["status"] = "AWAITING_CLINICIAN_APPROVAL"
                res["ticket"] = ticket.model_dump()
                res["pending_actions"] = pending_actions
                res["pending_action"] = {
                    "action_type": action_type_label,
                    "params": first_act
                }
            
            # Sanitize final summary text to guarantee clean Markdown string
            if res.get("final_summary"):
                res["final_summary"] = extract_message_text(res["final_summary"])

            # Apply field-level RBAC filtering on final output
            return apply_field_level_rbac(res, user_role)
        else:
            # Multi-agent standard pipeline
            initial_state = {
                "patient_id": effective_patient_id,
                "user_prompt": req.prompt,
                "next_node": "IngestionAgent"
            }
            res = multi_agent_app.invoke(initial_state)
            if res.get("final_summary"):
                res["final_summary"] = extract_message_text(res["final_summary"])
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
    exec_count = len(final_state.get("execution_results", []))
    order_label = f"{exec_count} clinical orders" if exec_count > 1 else "Order"
    return {
        "status": "APPROVED",
        "message": f"Ticket {req.ticket_id} approved. {order_label} executed successfully.",
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


@app.get("/api/audit/incidents")
def list_audit_incidents(limit: int = 50):
    """
    Retrieve logged system, RBAC, and agent incidents for administrative and clinical governance review.
    """
    reports_dir = audit_tracker.reports_dir
    incidents = []
    if reports_dir.exists():
        event_files = sorted(reports_dir.glob("EVENT-*.json"), key=os.path.getmtime, reverse=True)
        for p in event_files[:limit]:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    incidents.append(json.load(f))
            except Exception:
                pass
    return {
        "total_incidents": len(incidents),
        "incidents": incidents
    }


@app.get("/api/audit/traces")
def list_audit_traces(limit: int = 50):
    """
    Retrieve all recorded transaction traces illustrating how instructions traveled through the platform.
    """
    trace_ids = audit_tracker.list_transaction_traces()
    traces = []
    for tid in trace_ids[:limit]:
        tr = audit_tracker.get_transaction_trace(tid)
        if tr:
            traces.append(tr)
    return {
        "total_traces": len(traces),
        "traces": traces
    }


@app.get("/api/audit/traces/{trace_id}")
def get_audit_trace(trace_id: str):
    """
    Retrieve a specific transaction journey trace by trace ID.
    """
    trace = audit_tracker.get_transaction_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Transaction trace '{trace_id}' not found.")
    return trace


@app.get("/api/audit/journey-log")
def get_journey_log():
    """
    Retrieve the append-only human-readable transaction journey audit log.
    """
    traces_dir = audit_tracker.reports_dir.parent / "transaction_traces"
    log_path = traces_dir / "audit_journey.log"
    if not log_path.exists():
        return {"log": "No transaction journey logs recorded yet."}
    with open(log_path, "r", encoding="utf-8") as f:
        return {"log": f.read()}
