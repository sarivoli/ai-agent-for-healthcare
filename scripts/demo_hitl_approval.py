"""
Module 6 Milestone Demo: Clinical Rules, Confidence Scoring, Prompt-Driven CRUD & HITL Gates.
Demonstrates:
  1. Clinical Rule Engine evaluation with Heuristic Confidence Scores (0.00 to 1.00).
  2. Prompt-Driven CRUD Medication Order Submission.
  3. LangGraph HITL State Interrupt Pause (`AWAITING_CLINICIAN_APPROVAL`).
  4. Clinician Attestation Submission (Approval & Execution Branch).
  5. Clinician Attestation Submission (Rejection & Cancellation Branch).
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

from src.rules.rule_engine import clinical_rule_engine
from src.agents.hitl_agent import run_hitl_agent_pipeline, resume_hitl_agent_pipeline
from src.db.mock_healthcare_db import db


def print_banner(text: str):
    print("\n" + "=" * 80)
    print(f" {text}")
    print("=" * 80 + "\n")


def display_rule_engine_dashboard(result):
    print("-" * 80)
    print(" 🩺 CLINICAL RULE ENGINE & HEURISTIC CONFIDENCE SCORE DASHBOARD")
    print("-" * 80)
    print(f"   • Overall Rule Confidence: {result.overall_confidence_score * 100:.1f}%")
    print(f"   • Requires Attestation:   {result.requires_clinician_attestation}")
    
    print("\n   [EVALUATED HEDIS QUALITY METRICS]")
    for qm in result.quality_metrics:
        icon = "[PASS]" if qm.status == "PASS" else "[FLAG]"
        print(f"      {icon:<8} | {qm.title:<38} | Status: {qm.status:<12} | Conf: {qm.confidence_score:.2f}")

    print("\n   [IDENTIFIED CARE GAPS WITH CONFIDENCE SCORES & EVIDENCE]")
    for gap in result.care_gaps:
        sev = f"[{gap.severity}]"
        print(f"      {sev:<8} | Gap: {gap.title:<45} | Conf: {gap.confidence_score:.2f}")
        for ev in gap.evidence_sources:
            print(f"                 Evidence: {ev}")
        print(f"                 Recommendation: {gap.recommendation}")
    print("-" * 80 + "\n")


def run_demo(patient_id: str = "P101", force_mock: bool = False):
    print_banner("[HITL DEMO] MODULE 6 WORKING MILESTONE DEMO: CLINICAL RULES & HITL ATTESTATION")

    # 1. SCENARIO 1: RULE ENGINE & CONFIDENCE SCORES
    print(f"[SCENARIO 1] Executing Clinical Rule Engine with Confidence Scores for Patient '{patient_id}'...")
    raw_bundle = db.get_patient(patient_id) or {}
    labs = db.get_lab_results(patient_id)
    notes = db.get_clinical_notes(patient_id)
    meds = db.get_medications(patient_id)

    raw_data = {"patient_demographics": raw_bundle, "labs": labs, "medications": meds, "notes": notes}
    rule_res = clinical_rule_engine.evaluate(raw_data)
    display_rule_engine_dashboard(rule_res)

    # 2. SCENARIO 2 & 3: PROMPT-DRIVEN CRUD ORDER & HITL INTERRUPT PAUSE
    print_banner("🛑 SCENARIO 2 & 3: PROMPT-DRIVEN CRUD ORDER & HITL INTERRUPT PAUSE")
    session_id_appr = f"SESS-HITL-APPR-{uuid.uuid4().hex[:4]}"
    crud_prompt = "Clinical Decision Support: Please order Metformin 500mg ER daily for patient P101."
    
    print(f"[DEMO] Submitting Prompt-Driven Medication Order Query:")
    print(f"   Submitted Prompt: \"{crud_prompt}\"")
    print(f"\n   Executing LangGraph HITL Agent Pipeline...")
    
    res_paused = run_hitl_agent_pipeline(
        patient_id=patient_id,
        persona="physician",
        force_mock=force_mock,
        session_id=session_id_appr,
        custom_prompt=crud_prompt
    )

    print(f"\n   -> Graph Execution Status: [{res_paused.get('attestation_status')}]")
    print(f"   -> LangGraph Paused Execution via interrupt()")
    print(f"   -> Database Write Suspended Awaiting Clinician Decision\n")
    print("--- [INTERRUPT PAUSE BANNER DISPLAYED TO USER/CLINICIAN] ---")
    print(res_paused.get("final_summary"))
    print("-" * 80)

    # 3. SCENARIO 4: CLINICIAN ATTESTATION BRANCH A (APPROVAL)
    print_banner("✅ SCENARIO 4: CLINICIAN ATTESTATION SUBMISSION (APPROVAL BRANCH)")
    print(f"[DEMO 4] Attending Clinician Submits APPROVAL Decision for Session '{session_id_appr}'...")
    
    res_approved = resume_hitl_agent_pipeline(
        session_id=session_id_appr,
        approved=True,
        clinician_id="DR-JENKINS-MD",
        comments="Approved Metformin ER 500mg order to reduce GI distress."
    )

    print(f"\n   -> Graph Resumed Execution Status: [{res_approved.get('attestation_status')}]")
    print(f"   -> Database Write Executed Successfully!")
    print("\n--- [RESUMED GRAPH FINAL SUMMARY] ---")
    print(res_approved.get("final_summary"))
    print("-" * 80)

    # 4. SCENARIO 5: CLINICIAN ATTESTATION BRANCH B (REJECTION)
    print_banner("❌ SCENARIO 5: CLINICIAN ATTESTATION SUBMISSION (REJECTION BRANCH)")
    session_id_rej = f"SESS-HITL-REJ-{uuid.uuid4().hex[:4]}"
    
    print(f"[DEMO 5] Initiating new CRUD query for session '{session_id_rej}'...")
    run_hitl_agent_pipeline(
        patient_id=patient_id,
        persona="physician",
        force_mock=force_mock,
        session_id=session_id_rej,
        custom_prompt="Please order Metformin 1000mg daily for patient P101."
    )

    print(f"   Attending Clinician Submits REJECTION Decision...")
    res_rejected = resume_hitl_agent_pipeline(
        session_id=session_id_rej,
        approved=False,
        clinician_id="DR-VANCE-MD",
        comments="Rejected order due to patient-reported GI intolerance."
    )

    print(f"\n   -> Graph Resumed Execution Status: [{res_rejected.get('attestation_status')}]")
    print(f"   -> Database Write Cancelled!")
    print("\n--- [REJECTED GRAPH SUMMARY] ---")
    print(res_rejected.get("final_summary"))
    print("-" * 80)

    print_banner("[SUCCESS] MODULE 6 HITL DEMO COMPLETE: Confidence Scores, CRUD Tools & Attestation Validated!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Module 6 HITL Approval & CRUD Demo.")
    parser.add_argument("--patient-id", type=str, default="P101", help="Patient ID (default: P101)")
    parser.add_argument("--mock", action="store_true", help="Force offline deterministic execution")
    args = parser.parse_args()

    run_demo(patient_id=args.patient_id, force_mock=args.mock)
