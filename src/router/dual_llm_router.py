"""
Dual-LLM Router Engine & Zero Data Retention (ZDR) Privacy Proxy.
Orchestrates dynamic privacy-aware routing between Local LLM (Ollama Llama-3)
and Cloud LLM (Gemini 3.6 Flash) based on real-time PHI classification.
"""

import time
import uuid
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from src.router.phi_classifier import phi_classifier, PHIScanResult
from src.router.llm_providers import LocalLLMProvider, CloudLLMProvider
from src.security.audit_tracker import audit_tracker
from src.security.quota_manager import quota_manager, QuotaContext


class DualLLMRoutingResult(BaseModel):
    """Result object returned by the Dual-LLM Router Engine."""
    session_id: str
    route_selected: str  # 'LOCAL_PHI_ROUTE' | 'CLOUD_DEIDENTIFIED_ROUTE'
    zdr_enforced: bool
    phi_scan: PHIScanResult
    deidentification_proxy_used: bool = False
    raw_response: str
    final_response: str
    latency_seconds: float = 0.0


class DualLLMRouterNode:
    """
    LangGraph Node & Privacy Proxy managing Dual-LLM Routing.
    Protects patient privacy by directing sensitive PHI to Local LLM (ZDR)
    and de-identified workloads to Cloud LLM.
    """

    def __init__(self):
        self.local_provider = LocalLLMProvider()
        self.cloud_provider = CloudLLMProvider()

    def route_query(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        force_route: Optional[str] = None,
        enable_deidentification_proxy: bool = True
    ) -> DualLLMRoutingResult:
        """
        Scans prompt for PHI and dynamically routes to Local vs Cloud LLM.
        """
        if not session_id:
            session_id = f"SESS-ROUTER-{uuid.uuid4().hex[:6]}"

        start_time = time.perf_counter()

        # Step 1: Real-time PHI Classification
        phi_scan = phi_classifier.scan_text(prompt)

        # Step 2: Determine Route
        if force_route:
            selected_route = force_route.upper().strip()
        elif phi_scan.contains_phi:
            selected_route = "LOCAL_PHI_ROUTE"
        else:
            selected_route = "CLOUD_DEIDENTIFIED_ROUTE"

        # Step 3: Execute Route & Privacy Governance
        deidentification_used = False
        zdr_enforced = False

        if selected_route == "LOCAL_PHI_ROUTE":
            # Route raw PHI payload strictly to Local LLM (ZDR Enforced)
            res = self.local_provider.invoke(prompt)
            raw_output = res.get("content", "")
            final_output = raw_output
            zdr_enforced = True

        else:
            # Cloud Route requested
            if phi_scan.contains_phi and enable_deidentification_proxy:
                # De-identification Proxy: Redact PHI -> Cloud LLM -> Re-identify Output
                deidentified_prompt = phi_scan.redacted_text
                res = self.cloud_provider.invoke(deidentified_prompt)
                raw_output = res.get("content", "")
                final_output = phi_classifier.reidentify_text(raw_output, phi_scan.phi_token_map)
                deidentification_used = True
                zdr_enforced = False
            else:
                # Clean payload (no PHI) -> Direct Cloud Execution
                res = self.cloud_provider.invoke(prompt)
                raw_output = res.get("content", "")
                final_output = raw_output
                zdr_enforced = False

        total_latency = time.perf_counter() - start_time

        return DualLLMRoutingResult(
            session_id=session_id,
            route_selected=selected_route,
            zdr_enforced=zdr_enforced,
            phi_scan=phi_scan,
            deidentification_proxy_used=deidentification_used,
            raw_response=raw_output,
            final_response=final_output,
            latency_seconds=round(total_latency, 3)
        )


# Global router node instance
dual_llm_router = DualLLMRouterNode()


def run_dual_llm_router_pipeline(
    prompt: str,
    session_id: Optional[str] = None,
    force_route: Optional[str] = None
) -> DualLLMRoutingResult:
    """Entry point function for executing Dual-LLM Router pipeline."""
    return dual_llm_router.route_query(
        prompt=prompt,
        session_id=session_id,
        force_route=force_route
    )
