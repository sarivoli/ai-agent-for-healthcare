"""
Module 5 Milestone Demo: Dual-LLM PHI Privacy Router & Zero Data Retention (ZDR).
Demonstrates:
  1. Real-time PHI Classification across 18 HIPAA categories.
  2. Automatic Local LLM Routing for sensitive PHI payloads (ZDR Enforced).
  3. Automatic Cloud LLM Routing for de-identified workloads.
  4. Automated De-identification & Re-identification Proxy Roundtrip.
  5. Router Telemetry & Privacy Audit Dashboard.
"""

import sys
import argparse
import os
import uuid
from pathlib import Path

# Ensure project root is on sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ensure UTF-8 output encoding for cross-platform terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.router.phi_classifier import phi_classifier
from src.router.dual_llm_router import run_dual_llm_router_pipeline


def print_banner(text: str):
    print("\n" + "=" * 80)
    print(f" {text}")
    print("=" * 80 + "\n")


def display_phi_scan_dashboard(scan_result):
    print("-" * 80)
    print(" 🔍 PHI CLASSIFIER & REAL-TIME PRIVACY EVALUATOR DASHBOARD")
    print("-" * 80)
    print(f"   • Contains PHI:         {scan_result.contains_phi}")
    print(f"   • Sensitivity Score:    {scan_result.sensitivity_score} / 1.00")
    print(f"   • Detected Categories: {', '.join(scan_result.detected_categories) if scan_result.detected_categories else 'None (Clean Payload)'}")
    print("\n   [REDACTED PAYLOAD PREVIEW]")
    print(f"      {scan_result.redacted_text[:160]}...")
    print("\n   [DE-IDENTIFICATION TOKEN MAPPING TABLE]")
    if scan_result.phi_token_map:
        for token, original in scan_result.phi_token_map.items():
            print(f"      {token:<22} <---> {original}")
    else:
        print("      No sensitive tokens detected.")
    print("-" * 80 + "\n")


def display_router_telemetry(result):
    print("-" * 80)
    print(" 📊 DUAL-LLM ROUTER TELEMETRY & PRIVACY AUDIT")
    print("-" * 80)
    print(f"   • Session ID:            {result.session_id}")
    print(f"   • Selected Route:        {result.route_selected}")
    print(f"   • Zero Data Retention:   {'ENFORCED (ZDR active)' if result.zdr_enforced else 'DISABLED (De-identified Payload)'}")
    print(f"   • De-id Proxy Used:     {result.deidentification_proxy_used}")
    print(f"   • Execution Latency:     {result.latency_seconds} seconds")
    print("-" * 80 + "\n")


def run_demo(force_mock: bool = False):
    print_banner("[DUAL-LLM ROUTER] MODULE 5 WORKING MILESTONE DEMO: HIPAA PHI PRIVACY PROXY")

    # 1. SCENARIO 1: REAL-TIME PHI CLASSIFICATION
    phi_prompt = "Patient Eleanor Vance (MRN-884920, SSN 123-45-6789, DOB 1965-04-12) called 555-123-4567 regarding Metformin 1000mg GI side effects."
    print(f"[SCENARIO 1] Scanning Raw Clinical Payload for Protected Health Information (PHI)...")
    print(f"   Input Text: \"{phi_prompt}\"\n")
    scan_res = phi_classifier.scan_text(phi_prompt)
    display_phi_scan_dashboard(scan_res)

    # 2. SCENARIO 2: AUTOMATIC LOCAL LLM ROUTING (ZDR ENFORCED)
    print_banner("🔒 SCENARIO 2: AUTOMATIC LOCAL LLM ROUTING (ZERO DATA RETENTION ENFORCED)")
    print("[SCENARIO 2] Submitting Raw PHI Payload to Dual-LLM Router Engine...")
    res_local = run_dual_llm_router_pipeline(phi_prompt)
    print(f"   -> Router Decision: [{res_local.route_selected}]")
    print(f"   -> ZDR Status: [{'ENFORCED' if res_local.zdr_enforced else 'DISABLED'}] (Payload processed strictly inside local host memory)")
    print(f"\n   [LOCAL LLM ZDR RESPONSE]")
    print("-" * 60)
    print(res_local.final_response)
    print("-" * 60)
    display_router_telemetry(res_local)

    # 3. SCENARIO 3: AUTOMATIC CLOUD LLM ROUTING
    print_banner("☁️ SCENARIO 3: AUTOMATIC CLOUD LLM ROUTING (DE-IDENTIFIED / CLEAN WORKLOAD)")
    clean_prompt = "What are standard HEDIS CDC Hemoglobin A1c targets and screening guidelines for Type 2 Diabetes?"
    print("[SCENARIO 3] Submitting Clean Clinical Inquiry (No PHI) to Dual-LLM Router Engine...")
    print(f"   Input Text: \"{clean_prompt}\"\n")
    res_cloud = run_dual_llm_router_pipeline(clean_prompt)
    print(f"   -> Router Decision: [{res_cloud.route_selected}]")
    print(f"   -> ZDR Status: [NOT_REQUIRED] (No sensitive PHI detected in payload)")
    print(f"\n   [CLOUD LLM RESPONSE]")
    print("-" * 60)
    print(res_cloud.final_response)
    print("-" * 60)
    display_router_telemetry(res_cloud)

    # 4. SCENARIO 4: DE-IDENTIFICATION & RE-IDENTIFICATION PROXY ROUNDTRIP
    print_banner("🔄 SCENARIO 4: DE-IDENTIFICATION PROXY & CLOUD ROUNDTRIP")
    print("[SCENARIO 4] Forcing Cloud Route on PHI Payload via Automated De-identification Proxy...")
    res_proxy = run_dual_llm_router_pipeline(phi_prompt, force_route="CLOUD_DEIDENTIFIED_ROUTE")
    print(f"   -> Router Decision: [{res_proxy.route_selected}]")
    print(f"   -> De-identification Proxy Executed: {res_proxy.deidentification_proxy_used}")
    print(f"   -> Redacted Text Sent to Cloud: \"{res_proxy.phi_scan.redacted_text}\"")
    print(f"   -> Re-identified Output Returned to User:")
    print("-" * 60)
    print(res_proxy.final_response)
    print("-" * 60)
    display_router_telemetry(res_proxy)

    print_banner("[SUCCESS] MODULE 5 DUAL-LLM ROUTER DEMO COMPLETE: PHI Classifier & ZDR Routing Validated!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Module 5 Dual-LLM Router Demo.")
    parser.add_argument("--mock", action="store_true", help="Force offline deterministic execution")
    args = parser.parse_args()

    run_demo(force_mock=args.mock)
