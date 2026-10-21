"""
Fault-Tolerant Input Persistence & Agent Exception Interceptor.
Prevents user input loss on programming or infrastructure exceptions and provides automatic draft recovery.
"""

from typing import Dict, Any, Optional, Callable
from functools import wraps
import traceback
from datetime import datetime, timezone
from src.security.audit_tracker import audit_tracker


class DraftStore:
    """In-memory draft store persisting user inputs per session thread."""

    def __init__(self):
        self._drafts: Dict[str, Dict[str, Any]] = {}

    def save_draft(self, thread_id: str, prompt: str, metadata: Optional[Dict[str, Any]] = None):
        self._drafts[thread_id] = {
            "thread_id": thread_id,
            "prompt": prompt,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def get_draft(self, thread_id: str) -> Optional[Dict[str, Any]]:
        return self._drafts.get(thread_id)

    def clear_draft(self, thread_id: str):
        if thread_id in self._drafts:
            del self._drafts[thread_id]


# Global Draft Store Singleton
draft_store = DraftStore()


import time
import uuid

def fault_tolerant_agent_execute(
    thread_id: str,
    prompt: str,
    execution_fn: Callable[[], Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Executes an agent workflow with input persistence and exception interception.
    Saves user input to draft store before execution.
    If an exception occurs, logs audit telemetry, preserves the prompt input, and returns a graceful error fallback.
    """
    draft_store.save_draft(thread_id, prompt)

    try:
        result = execution_fn()
        # On clean execution, clear the draft
        draft_store.clear_draft(thread_id)
        return result
    except Exception as exc:
        err_stack = traceback.format_exc()
        incident_id = f"INC-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}"
        
        # Log incident to security audit tracker
        audit_tracker.log_event(
            event_type="AGENT_EXECUTION_EXCEPTION",
            details={
                "incident_id": incident_id,
                "thread_id": thread_id,
                "prompt": prompt,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "traceback": err_stack[:500]
            }
        )

        return {
            "status": "agent_error",
            "incident_id": incident_id,
            "error_type": type(exc).__name__,
            "error_message": f"Execution error: {str(exc)}",
            "user_message": (
                "We encountered an unexpected issue while processing your clinical request. "
                f"Your input prompt has been safely preserved in draft memory. Our clinical operations audit team "
                f"has logged this incident (Reference: {incident_id}) for review."
            ),
            "user_input_preserved": True,
            "draft_prompt": prompt,
            "thread_id": thread_id,
            "recommendation": "Your input has been safely preserved. You may click 'Restore Draft' to review or adjust your prompt, or try again."
        }
