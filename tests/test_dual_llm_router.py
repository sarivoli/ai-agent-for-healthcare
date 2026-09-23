"""
Unit and Integration Test Suite for Module 5: Dual-LLM Routing & PHI Protection.
Tests PHI classification accuracy, ZDR local routing, cloud routing, and de-identification proxy roundtrip.
"""

import pytest
from src.router.phi_classifier import phi_classifier, PHIScanResult
from src.router.dual_llm_router import run_dual_llm_router_pipeline, dual_llm_router


def test_phi_classifier_detection():
    """Verifies regex & heuristic PHI detection across 18 HIPAA category categories."""
    raw_prompt = "Patient Eleanor Vance (MRN-884920, SSN 123-45-6789, DOB 1965-04-12) phone 555-123-4567."
    scan = phi_classifier.scan_text(raw_prompt)

    assert scan.contains_phi is True
    assert scan.sensitivity_score >= 0.8
    assert "SSN" in scan.detected_categories
    assert "MRN" in scan.detected_categories
    assert "PHONE" in scan.detected_categories
    assert "DOB" in scan.detected_categories
    assert "PATIENT_NAME" in scan.detected_categories
    assert "[SSN_1]" in scan.phi_token_map
    assert scan.phi_token_map["[SSN_1]"] == "123-45-6789"


def test_dual_llm_routing_local_phi():
    """Verifies that payloads containing PHI automatically route to LOCAL_PHI_ROUTE with ZDR Enforced."""
    phi_prompt = "Eleanor Vance (MRN-884920) reports Metformin stomach upset."
    result = run_dual_llm_router_pipeline(prompt=phi_prompt)

    assert result.route_selected == "LOCAL_PHI_ROUTE"
    assert result.zdr_enforced is True
    assert result.phi_scan.contains_phi is True
    assert "LOCAL ZDR MODEL" in result.final_response or "ZDR" in result.final_response


def test_dual_llm_routing_cloud_clean():
    """Verifies that clean clinical prompts without PHI route to CLOUD_DEIDENTIFIED_ROUTE."""
    clean_prompt = "What are standard HEDIS CDC Hemoglobin A1c guidelines for Type 2 Diabetes?"
    result = run_dual_llm_router_pipeline(prompt=clean_prompt)

    assert result.route_selected == "CLOUD_DEIDENTIFIED_ROUTE"
    assert result.phi_scan.contains_phi is False


def test_deidentification_reidentification_proxy():
    """Verifies forced cloud route with automated de-identification and re-identification proxy roundtrip."""
    phi_prompt = "Patient Eleanor Vance (MRN-884920) needs HbA1c review."
    result = dual_llm_router.route_query(
        prompt=phi_prompt,
        force_route="CLOUD_DEIDENTIFIED_ROUTE",
        enable_deidentification_proxy=True
    )

    assert result.route_selected == "CLOUD_DEIDENTIFIED_ROUTE"
    assert result.deidentification_proxy_used is True
    assert "[PATIENT_NAME_" in result.phi_scan.redacted_text
    # Re-identified final response should contain original patient name
    assert "Eleanor Vance" in result.final_response


def test_phi_classifier_edge_cases():
    """Verifies classifier behavior on empty payloads and non-PHI clinical text."""
    empty_scan = phi_classifier.scan_text("")
    assert empty_scan.contains_phi is False
    assert empty_scan.redacted_text == ""

    clean_scan = phi_classifier.scan_text("Explain the mechanism of action for Lisinopril.")
    assert clean_scan.contains_phi is False
    assert len(clean_scan.detected_categories) == 0
