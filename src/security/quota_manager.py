"""
Role-Based Token Quota & Extensible Strategy Governance Engine.
Enforces enterprise rate limits, token quotas, and professional conversation holds
using a pluggable Strategy Pattern for extensible business logic.
"""

import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, Tuple, Callable
from pydantic import BaseModel, Field


class QuotaState(str, Enum):
    ACTIVE = "ACTIVE"
    GRACE_PERIOD = "GRACE_PERIOD"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"


class QuotaContext(BaseModel):
    """Business context used to calculate dynamic token quotas."""
    role: str
    department: Optional[str] = None  # e.g., 'ICU', 'Oncology', 'Cardiology'
    patient_tier: Optional[str] = None  # e.g., 'vip', 'standard'
    acuity_level: Optional[str] = None  # e.g., 'critical', 'moderate', 'low'
    custom_attributes: Dict[str, Any] = Field(default_factory=dict)


# Default Token Quotas per Role
DEFAULT_ROLE_QUOTAS: Dict[str, int] = {
    "supervisor": 15000,
    "clinician": 8000,
    "patient_vip": 5000,
    "patient_standard": 2000
}

DEFAULT_GRACE_BUFFER_PERCENT: float = 0.20


# ==============================================================================
# PLUGGABLE QUOTA STRATEGIES (EXTENSIBLE BUSINESS LOGIC)
# ==============================================================================

class BaseQuotaStrategy(ABC):
    """Abstract Strategy interface for calculating token quotas and grace caps."""
    
    @abstractmethod
    def calculate_quota(self, context: QuotaContext) -> Tuple[int, int]:
        """
        Computes (base_quota, grace_limit) for the given business context.
        """
        pass


class RoleBasedQuotaStrategy(BaseQuotaStrategy):
    """
    Standard enterprise role-based quota strategy with optional env overrides.
    """
    def __init__(
        self,
        base_quotas: Optional[Dict[str, int]] = None,
        grace_percent: float = DEFAULT_GRACE_BUFFER_PERCENT
    ):
        self.base_quotas = base_quotas or dict(DEFAULT_ROLE_QUOTAS)
        self.grace_percent = grace_percent
        self._load_env_overrides()

    def _load_env_overrides(self):
        for role in DEFAULT_ROLE_QUOTAS:
            env_var = f"QUOTA_{role.upper()}"
            val = os.getenv(env_var)
            if val and val.isdigit():
                self.base_quotas[role] = int(val)

    def calculate_quota(self, context: QuotaContext) -> Tuple[int, int]:
        role_clean = context.role.lower().strip()
        base_quota = self.base_quotas.get(role_clean, 2000)
        grace_limit = int(base_quota * (1.0 + self.grace_percent))
        return base_quota, grace_limit


class DepartmentTierQuotaStrategy(BaseQuotaStrategy):
    """
    Extends standard quotas with department multipliers (e.g. ICU receives 2x quota).
    """
    DEPARTMENT_MULTIPLIERS = {
        "icu": 2.0,
        "emergency": 1.75,
        "oncology": 1.5,
        "cardiology": 1.3
    }

    def __init__(self, fallback_strategy: Optional[BaseQuotaStrategy] = None):
        self.fallback_strategy = fallback_strategy or RoleBasedQuotaStrategy()

    def calculate_quota(self, context: QuotaContext) -> Tuple[int, int]:
        base_quota, grace_limit = self.fallback_strategy.calculate_quota(context)
        dept = (context.department or "").lower().strip()
        multiplier = self.DEPARTMENT_MULTIPLIERS.get(dept, 1.0)

        adjusted_base = int(base_quota * multiplier)
        adjusted_grace = int(grace_limit * multiplier)
        return adjusted_base, adjusted_grace


class CustomRuleQuotaStrategy(BaseQuotaStrategy):
    """
    Allows registering custom business logic via a lambda or callback function.
    """
    def __init__(self, rule_func: Callable[[QuotaContext], Tuple[int, int]]):
        self.rule_func = rule_func

    def calculate_quota(self, context: QuotaContext) -> Tuple[int, int]:
        return self.rule_func(context)


# ==============================================================================
# QUOTA MANAGER CONTROLLER
# ==============================================================================

class QuotaManager:
    """
    Manages session token budgets, tracks cumulative usage,
    and delegates quota calculations to the active BaseQuotaStrategy.
    """
    def __init__(
        self,
        strategy: Optional[BaseQuotaStrategy] = None,
        grace_buffer_percent: Optional[float] = None
    ):
        if strategy:
            self.strategy = strategy
        elif grace_buffer_percent is not None:
            self.strategy = RoleBasedQuotaStrategy(grace_percent=grace_buffer_percent)
        else:
            self.strategy = RoleBasedQuotaStrategy()
        self._session_usage: Dict[str, int] = {}

    def set_strategy(self, strategy: BaseQuotaStrategy):
        """Allows dynamic runtime replacement of the quota business logic."""
        self.strategy = strategy

    def get_role_quota(self, role: str) -> int:
        """Helper for backward compatibility."""
        context = QuotaContext(role=role)
        base, _ = self.strategy.calculate_quota(context)
        return base

    def get_role_grace_limit(self, role: str) -> int:
        """Helper for backward compatibility."""
        context = QuotaContext(role=role)
        _, grace = self.strategy.calculate_quota(context)
        return grace

    def get_session_usage(self, session_id: str) -> int:
        return self._session_usage.get(session_id, 0)

    def record_usage(self, session_id: str, tokens: int) -> int:
        current = self._session_usage.get(session_id, 0)
        self._session_usage[session_id] = current + tokens
        return self._session_usage[session_id]

    def reset_session(self, session_id: str):
        self._session_usage.pop(session_id, None)

    def evaluate_quota(
        self,
        session_id: str,
        role: str,
        context: Optional[QuotaContext] = None,
        incoming_tokens_est: int = 0
    ) -> Tuple[QuotaState, Dict[str, Any]]:
        """
        Evaluates current quota status using the active strategy.
        """
        if context is None:
            context = QuotaContext(role=role)

        current_usage = self.get_session_usage(session_id)
        projected_usage = current_usage + incoming_tokens_est
        base_quota, grace_limit = self.strategy.calculate_quota(context)

        details = {
            "session_id": session_id,
            "role": role,
            "department": context.department,
            "current_tokens": current_usage,
            "projected_tokens": projected_usage,
            "base_quota": base_quota,
            "grace_limit": grace_limit,
            "remaining_base_tokens": max(0, base_quota - current_usage),
            "remaining_grace_tokens": max(0, grace_limit - current_usage)
        }

        if projected_usage <= base_quota:
            return QuotaState.ACTIVE, details
        elif projected_usage <= grace_limit:
            return QuotaState.GRACE_PERIOD, details
        else:
            return QuotaState.LIMIT_EXCEEDED, details

    def get_professional_closure_message(
        self,
        role: str,
        session_id: str,
        patient_name: Optional[str] = None
    ) -> str:
        role_clean = role.lower().strip()
        usage = self.get_session_usage(session_id)
        limit = self.get_role_grace_limit(role)

        if "patient" in role_clean:
            salutation = f"Dear {patient_name}," if patient_name else "Dear Patient,"
            return (
                f"# NOTICE: SESSION CONVERSATION LIMIT REACHED\n\n"
                f"{salutation}\n\n"
                f"You have reached your allocated conversational allowance for this session "
                f"({usage:,} tokens used of {limit:,} maximum allowed).\n\n"
                f"To ensure patient safety and care continuity, complex clinical questions require direct clinical review. "
                f"Please take one of the following next steps:\n"
                f"1. **Primary Care Consultation:** Contact your care team at **1-800-555-CARE** to review your recent labs or health plan.\n"
                f"2. **Patient Portal:** Log in to your health portal to send a secure message directly to your provider.\n"
                f"3. **Urgent Symptoms:** If you are experiencing chest pain, severe shortness of breath, or a medical emergency, "
                f"call **911** or visit the nearest emergency department immediately.\n\n"
                f"*Thank you for using our healthcare portal.*"
            )
        else:
            return (
                f"# ADMINISTRATIVE ALERT: SESSION TOKEN QUOTA EXCEEDED\n\n"
                f"**Session ID:** `{session_id}` | **Assigned Role:** `{role}`\n"
                f"**Token Status:** `{usage:,} / {limit:,}` tokens consumed (100% of base quota + grace buffer).\n\n"
                f"### System Action Taken:\n"
                f"The active LangGraph conversation has been paused to enforce institutional governance and cost boundaries.\n\n"
                f"### Resolution Pathways:\n"
                f"- **Start New Clinical Session:** Archive this case summary and initiate a new session ID for subsequent analysis.\n"
                f"- **Elevated Quota Request:** Contact your Health System IT Administrator to request an expanded token allocation for your role.\n"
                f"- **Audit Record:** A full telemetry report of all tools and tokens consumed has been archived to the audit log."
            )


# Global singleton quota manager
quota_manager = QuotaManager()
