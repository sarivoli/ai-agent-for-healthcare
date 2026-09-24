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
        
        # Log incident to security audit tracker
        audit_tracker.log_event(
            event_type="AGENT_EXECUTION_EXCEPTION",
            details={
                "thread_id": thread_id,
                "error": str(exc),
                "traceback": err_stack[:500]
            }
        )

        return {
            "status": "agent_error",
            "error_type": type(exc).__name__,
            "error_message": f"Execution error: {str(exc)}",
            "user_input_preserved": True,
            "draft_prompt": prompt,
            "thread_id": thread_id,
            "recommendation": "Your input has been safely preserved. You may retry your request or adjust your prompt."
        }
