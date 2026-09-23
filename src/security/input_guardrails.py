"""
Enterprise Input Guardrails & Prompt Injection Defense Engine.
Detects adversarial prompt injections, jailbreak attempts, system prompt exfiltrations,
and out-of-scope probes before queries reach the LLM or tools.
"""

import re
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class GuardrailResult(BaseModel):
    """Result of an input guardrail scan."""
    is_allowed: bool
    violation_category: Optional[str] = None
    reason: Optional[str] = None
    refusal_message: Optional[str] = None


# Adversarial Prompt Injection & Jailbreak Patterns
JAILBREAK_PATTERNS: List[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+|any\s+|prior\s+|previous\s+)*(instructions|prompts|rules|guidelines|constraints)", re.IGNORECASE),
    re.compile(r"(disregard|forget|bypass|override)\s+(all\s+|any\s+|prior\s+|previous\s+)*(rules|guidelines|instructions|safety|guardrails|constraints|protocols)", re.IGNORECASE),
    re.compile(r"\b(you\s+are\s+now\s+(in\s+)?|switch\s+to\s+|enable\s+|enter\s+|activate\s+)?(dan\s+mode|developer\s+mode|unrestricted\s+mode|god\s+mode|evil\s+bot)\b", re.IGNORECASE),
    re.compile(r"\bdeveloper\s+mode\b", re.IGNORECASE),
    re.compile(r"\b(system\s+override|admin\s+override|emergency\s+override|root\s+access)\b", re.IGNORECASE),
    re.compile(r"\bdo\s+anything\s+now\b", re.IGNORECASE),
    re.compile(r"\bact\s+as\s+an\s+unfiltered\b", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
]

# System Prompt & Internal Configuration Exfiltration Patterns
EXFILTRATION_PATTERNS: List[re.Pattern] = [
    re.compile(r"(print|reveal|show|dump|repeat|output|leak|share)\s+(me\s+|us\s+)?(your\s+|the\s+|hidden\s+)*(system\s+prompt|initial\s+instructions|system\s+instructions|developer\s+prompt|meta\s+prompt|hidden\s+prompt)", re.IGNORECASE),
    re.compile(r"(what\s+(is|are)\s+(your|the)\s+)(exact\s+|underlying\s+|hidden\s+)?(instructions|rules|system\s+prompt)", re.IGNORECASE),
    re.compile(r"(show|tell|reveal|what\s+is)\s+(me\s+|us\s+)?(the\s+)?(api\s+key|database\s+password|internal\s+secret|auth\s+token)", re.IGNORECASE),
    re.compile(r"(show|display|reveal|dump|print)\s+(me\s+|us\s+)?(the\s+|all\s+|internal\s+)*(token\s+monitor|token\s+costs?|telemetry|admin\s+reports?|quota\s+internals?|quota\s+usage)", re.IGNORECASE),
    re.compile(r"\b(exfiltrate|leak|dump)\b.*(telemetry|api\s+key|secret|token|quota|prompt)", re.IGNORECASE),
]

# Non-Clinical Exploit & Payload Patterns
EXPLOIT_PATTERNS: List[re.Pattern] = [
    re.compile(r"(\bexec\b|\beval\b|\bsystem\b|\bsubprocess\b)\s*\(", re.IGNORECASE),
    re.compile(r"(\bunion\s+select\b|\bdrop\s+table\b|\binsert\s+into\b.*\bvalues\b)", re.IGNORECASE),
    re.compile(r"(<script\b|javascript:|onerror\s*=)", re.IGNORECASE),
]


class InputGuardrailEngine:
    """
    Scans incoming prompts for security violations, jailbreaks, and prompt injections.
    Terminates malicious queries at the entry boundary with zero LLM token consumption.
    """

    def scan(self, user_prompt: str) -> GuardrailResult:
        """
        Executes comprehensive defense-in-depth scans on an incoming user prompt.
        """
        if not user_prompt or not isinstance(user_prompt, str):
            return GuardrailResult(
                is_allowed=False,
                violation_category="INVALID_INPUT",
                reason="Prompt must be a non-empty string.",
                refusal_message=self._build_refusal_message("INVALID_INPUT", "Empty or invalid prompt payload.")
            )

        prompt_clean = user_prompt.strip()

        # 1. Check for Jailbreak / Prompt Injection Patterns
        for pattern in JAILBREAK_PATTERNS:
            if pattern.search(prompt_clean):
                return GuardrailResult(
                    is_allowed=False,
                    violation_category="JAILBREAK_ATTEMPT",
                    reason=f"Prompt triggered security rule: '{pattern.pattern}'",
                    refusal_message=self._build_refusal_message(
                        "JAILBREAK_ATTEMPT",
                        "The submitted prompt contains instructions attempting to override system behavior or safety constraints."
                    )
                )

        # 2. Check for System Prompt / Telemetry Exfiltration Probes
        for pattern in EXFILTRATION_PATTERNS:
            if pattern.search(prompt_clean):
                return GuardrailResult(
                    is_allowed=False,
                    violation_category="SYSTEM_EXFILTRATION_PROBE",
                    reason=f"Prompt attempted to extract internal configuration or telemetry.",
                    refusal_message=self._build_refusal_message(
                        "SYSTEM_EXFILTRATION_PROBE",
                        "Requests to inspect internal system prompts, developer instructions, or platform telemetry are prohibited."
                    )
                )

        # 3. Check for Malicious Exploit Payloads
        for pattern in EXPLOIT_PATTERNS:
            if pattern.search(prompt_clean):
                return GuardrailResult(
                    is_allowed=False,
                    violation_category="EXPLOIT_PAYLOAD_DETECTED",
                    reason="Prompt contains malicious syntax or script execution attempts.",
                    refusal_message=self._build_refusal_message(
                        "EXPLOIT_PAYLOAD_DETECTED",
                        "Potentially hazardous script, command, or query syntax was detected and blocked."
                    )
                )

        # Prompt passed all input guardrails
        return GuardrailResult(is_allowed=True)

    def _build_refusal_message(self, category: str, details: str) -> str:
        """Generates an enterprise-grade security refusal notice."""
        return (
            f"# SECURITY NOTICE: REQUEST INTERCEPTED BY INPUT GUARDRAILS\n\n"
            f"**Violation Category:** `{category}`\n\n"
            f"**Policy Explanation:**\n"
            f"{details}\n\n"
            f"### Healthcare Safety Policy:\n"
            f"This enterprise clinical platform strictly enforces medical AI alignment and data governance. "
            f"All prompts must relate to clinical inquiries, patient record synthesis, or care quality audits. "
            f"Adversarial overrides, prompt extractions, and unauthorized commands are automatically logged for security review.\n\n"
            f"*If you believe this detection was in error, please contact your Health System IT Security Administrator.*"
        )


# Global singleton instance
input_guardrail_engine = InputGuardrailEngine()
