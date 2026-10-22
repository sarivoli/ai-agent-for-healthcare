"""
LangGraph Session Memory Checkpointer & Async HITL Ticket Manager.
Manages persistent state snapshots across user sessions and tracks Human-in-the-Loop tickets with status ETAs.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field
from langgraph.checkpoint.memory import MemorySaver


# Global LangGraph Memory Checkpointer Singleton
session_checkpointer = MemorySaver()


class HITLTicket(BaseModel):
    """Data model for pending Human-in-the-Loop attestation tickets."""
    ticket_id: str
    thread_id: str
    patient_id: str
    action_type: str
    action_params: Dict[str, Any] = Field(default_factory=dict)
    pending_actions: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "AWAITING_CLINICIAN_APPROVAL"  # AWAITING_CLINICIAN_APPROVAL | APPROVED | REJECTED | EXPIRED_REJECTED
    estimated_eta: str = "15 minutes (Clinician Queue)"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decided_at: Optional[str] = None
    clinician_notes: Optional[str] = None


class HITLTicketManager:
    """
    In-memory / Persistent registry for Human-in-the-Loop tickets.
    Enables async polling, ticket tracking, and status retrieval across user sessions.
    """

    def __init__(self):
        self._tickets: Dict[str, HITLTicket] = {}  # ticket_id -> HITLTicket
        self._thread_map: Dict[str, str] = {}     # thread_id -> ticket_id

    def create_ticket(
        self,
        thread_id: str,
        patient_id: str,
        action_type: str,
        action_params: Dict[str, Any],
        pending_actions: Optional[List[Dict[str, Any]]] = None,
        estimated_eta: str = "15 minutes (Clinician Queue)"
    ) -> HITLTicket:
        """Create a new pending HITL attestation ticket."""
        ticket_id = f"HITL-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        act_list = pending_actions if pending_actions is not None else ([action_params] if action_params else [])
        ticket = HITLTicket(
            ticket_id=ticket_id,
            thread_id=thread_id,
            patient_id=patient_id,
            action_type=action_type,
            action_params=action_params,
            pending_actions=act_list,
            status="AWAITING_CLINICIAN_APPROVAL",
            estimated_eta=estimated_eta
        )
        self._tickets[ticket_id] = ticket
        self._thread_map[thread_id] = ticket_id
        return ticket

    def get_ticket_by_id(self, ticket_id: str) -> Optional[HITLTicket]:
        """Retrieve ticket by unique ticket ID."""
        return self._tickets.get(ticket_id)

    def get_ticket_by_thread(self, thread_id: str) -> Optional[HITLTicket]:
        """Retrieve ticket by thread ID."""
        ticket_id = self._thread_map.get(thread_id)
        if ticket_id:
            return self._tickets.get(ticket_id)
        return None

    def get_pending_tickets(self) -> List[HITLTicket]:
        """Get all pending tickets waiting for clinician attestation."""
        return [
            t for t in self._tickets.values()
            if t.status == "AWAITING_CLINICIAN_APPROVAL"
        ]

    def update_ticket_status(
        self,
        ticket_id: str,
        status: str,
        clinician_notes: Optional[str] = None
    ) -> Optional[HITLTicket]:
        """Update ticket status (APPROVED | REJECTED | EXPIRED_REJECTED)."""
        ticket = self._tickets.get(ticket_id)
        if ticket:
            ticket.status = status
            ticket.decided_at = datetime.now(timezone.utc).isoformat()
            ticket.clinician_notes = clinician_notes
            return ticket
        return None


# Global HITL Ticket Manager Instance
ticket_manager = HITLTicketManager()
