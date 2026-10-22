"""
Unit and Integration Tests for Dynamic Patient Context & Scenario Prompt Alignment.
Verifies that patient context (P101 vs P102) is preserved, prompt messages match execution,
and clinical summaries dynamically reflect the chosen patient without hardcoding.
"""

import pytest
from src.agents.hitl_agent import run_hitl_agent_pipeline
from src.api.server import process_chat_request, ChatRequest
from src.db.mock_healthcare_db import HealthcareDatabase


@pytest.fixture
def clean_db():
    db = HealthcareDatabase()
    db.reset()
    return db


def test_p102_clinical_summary_reflection(clean_db):
    """Verify that clinical summary for P102 accurately reflects Marcus Brody and his lab profile."""
    res = run_hitl_agent_pipeline(
        patient_id="P102",
        role="clinician",
        custom_prompt="Get patient summary for P102 and check recent lab results."
    )

    summary = res.get("final_summary", "")
    assert "Marcus Brody" in summary or "P102" in summary
    assert ("Hyperlipidemia" in summary or "Cholesterol" in summary or "lipid" in summary.lower())
    # Should include Total Cholesterol lab
    assert "Total Cholesterol" in summary or "245" in summary
    # Should NOT attribute P101's diabetes to P102
    assert "Eleanor Vance" not in summary


def test_p101_clinical_summary_reflection(clean_db):
    """Verify that clinical summary for P101 accurately reflects Eleanor Vance and her diabetes profile."""
    res = run_hitl_agent_pipeline(
        patient_id="P101",
        role="clinician",
        custom_prompt="Get patient summary for P101 and check recent lab results."
    )

    summary = res.get("final_summary", "")
    assert "Eleanor Vance" in summary or "P101" in summary
    assert "MRN-884920" in summary
    assert "Diabetes" in summary
    assert "Hemoglobin A1c" in summary or "8.4" in summary
    assert "Marcus Brody" not in summary


def test_api_effective_patient_id_reconciliation():
    """Verify that if prompt explicitly requests P102, API synchronizes execution context to P102."""
    req = ChatRequest(
        prompt="Get patient summary for P102 and check recent lab results.",
        patient_id="P101",  # simulate stale client dropdown
        use_hitl=True
    )
    auth = "Bearer clinician_token"
    res = process_chat_request(req, authorization=auth)

    summary = res.get("final_summary", "")
    assert "Marcus Brody" in summary or "P102" in summary
    assert "Eleanor Vance" not in summary


def test_p102_care_gap_evaluation(clean_db):
    """Verify that HEDIS care gap evaluation for P102 targets lipid/cholesterol and avoids diabetic eye gaps."""
    res = run_hitl_agent_pipeline(
        patient_id="P102",
        role="clinician",
        custom_prompt="Analyze patient P102 for care gaps and HEDIS quality compliance."
    )

    summary = res.get("final_summary", "")
    # Should evaluate cholesterol/lipid or return compliant/suboptimal lipid metrics
    assert "Marcus Brody" in summary or "P102" in summary
    # Rule evaluation should be grounded in P102
    rule_eval = res.get("rule_evaluation") or {}
    quality_metrics = rule_eval.get("quality_metrics", [])
    metric_ids = [m.get("metric_id") for m in quality_metrics]
    assert any("SPC" in mid or "CHOL" in mid for mid in metric_ids) or "Total Cholesterol" in summary
