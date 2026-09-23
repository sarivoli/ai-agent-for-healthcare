"""
Unit and Integration Tests for Telemetry, Auditability & Role-Based Token Quota Governance.
"""

import json
import pytest
from src.security.quota_manager import QuotaManager, QuotaState
from src.security.audit_tracker import AuditTracker
from src.agents.single_agent import run_clinical_agent


@pytest.fixture
def test_quota_manager():
    return QuotaManager(grace_buffer_percent=0.20)


@pytest.fixture
def test_audit_tracker(tmp_path):
    return AuditTracker(reports_dir=tmp_path)


class TestQuotaManager:
    """Validates role-based quota policies, calculations, and message templates."""

    def test_role_quota_defaults(self, test_quota_manager):
        assert test_quota_manager.get_role_quota("supervisor") == 15000
        assert test_quota_manager.get_role_quota("clinician") == 8000
        assert test_quota_manager.get_role_quota("patient_vip") == 5000
        assert test_quota_manager.get_role_quota("patient_standard") == 2000

    def test_grace_limit_calculation(self, test_quota_manager):
        # 2000 * 1.20 = 2400
        assert test_quota_manager.get_role_grace_limit("patient_standard") == 2400
        # 8000 * 1.20 = 9600
        assert test_quota_manager.get_role_grace_limit("clinician") == 9600

    def test_quota_state_transitions(self, test_quota_manager):
        session_id = "test-sess-states"
        # 1. Active: 1500 < 2000
        test_quota_manager.record_usage(session_id, 1500)
        state, details = test_quota_manager.evaluate_quota(session_id, "patient_standard")
        assert state == QuotaState.ACTIVE
        assert details["remaining_base_tokens"] == 500

        # 2. Grace Period: 2200 is between 2000 and 2400
        test_quota_manager.record_usage(session_id, 700)  # total 2200
        state, details = test_quota_manager.evaluate_quota(session_id, "patient_standard")
        assert state == QuotaState.GRACE_PERIOD
        assert details["remaining_grace_tokens"] == 200

        # 3. Limit Exceeded: 2500 > 2400
        test_quota_manager.record_usage(session_id, 300)  # total 2500
        state, details = test_quota_manager.evaluate_quota(session_id, "patient_standard")
        assert state == QuotaState.LIMIT_EXCEEDED

    def test_closure_messages_differentiation(self, test_quota_manager):
        patient_msg = test_quota_manager.get_professional_closure_message("patient_standard", "s1", "Eleanor")
        assert "SESSION CONVERSATION LIMIT REACHED" in patient_msg
        assert "Eleanor" in patient_msg
        assert "1-800-555-CARE" in patient_msg

        clinician_msg = test_quota_manager.get_professional_closure_message("clinician", "s2")
        assert "ADMINISTRATIVE ALERT" in clinician_msg
        assert "SESSION TOKEN QUOTA EXCEEDED" in clinician_msg


class TestAuditTracker:
    """Validates token extraction, evidence grounding, and report generation."""

    def test_grounding_audit_perfect_match(self, test_audit_tracker):
        retrieved_data = {
            "patient_name": "Eleanor Vance",
            "mrn": "MRN-884920",
            "labs": [{"name": "Hemoglobin A1c", "result_value": 8.4, "unit": "%"}],
            "medications": [{"drug_name": "Metformin 1000mg"}]
        }
        summary = "Patient Eleanor Vance (MRN-884920) has Hemoglobin A1c of 8.4% and is taking Metformin."
        audit = test_audit_tracker.audit_clinical_grounding(retrieved_data, summary)
        assert audit["grounding_score_percent"] == 100.0
        assert audit["hallucination_risk"] == "VERY_LOW"
        assert audit["verified_claims_count"] == 4

    def test_grounding_audit_missing_claims(self, test_audit_tracker):
        retrieved_data = {
            "patient_name": "Eleanor Vance",
            "mrn": "MRN-884920",
            "labs": [{"name": "Hemoglobin A1c", "result_value": 8.4, "unit": "%"}],
            "medications": [{"drug_name": "Insulin Glargine"}]
        }
        summary = "Patient Eleanor Vance attended clinic."
        audit = test_audit_tracker.audit_clinical_grounding(retrieved_data, summary)
        # Name is present, but MRN, HbA1c 8.4%, and Insulin are missing
        assert audit["grounding_score_percent"] < 50.0

    def test_session_report_generation_and_retrieval(self, test_audit_tracker):
        session_id = "test-sess-report"
        report = test_audit_tracker.generate_session_report(
            session_id=session_id,
            user_id="USR-99",
            role="clinician",
            patient_id="P101",
            persona="physician",
            latency_seconds=1.1,
            token_metrics={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150, "estimated_cost_usd": 0.0001},
            quota_details={"base_quota": 8000, "remaining_base_tokens": 7850},
            grounding_audit={"grounding_score_percent": 100.0, "hallucination_risk": "VERY_LOW"},
            tools_executed=[{"tool": "get_patient_demographics"}],
            final_summary="Test Summary"
        )
        assert report["session_id"] == session_id

        # Verify retrieval
        retrieved = test_audit_tracker.get_session_audit_report(session_id)
        assert retrieved is not None
        assert retrieved["user_context"]["user_id"] == "USR-99"
        assert retrieved["token_telemetry"]["total_tokens"] == 150


class TestSingleAgentGovernanceIntegration:
    """Validates LangGraph agent execution under quota governance."""

    def test_agent_active_quota_execution(self):
        result = run_clinical_agent(
            patient_id="P101",
            persona="physician",
            force_mock=True,
            role="supervisor",
            session_id="sess-active-test"
        )
        assert result["quota_status"] in ["ACTIVE", "GRACE_PERIOD"]
        assert "CLINICAL SUMMARY (SOAP BRIEF)" in result["final_summary"]
        assert result.get("telemetry_audit") is not None
        assert result["telemetry_audit"]["grounding_audit"]["grounding_score_percent"] == 100.0

    def test_agent_hard_quota_hold(self):
        from src.security.quota_manager import quota_manager
        session_id = "sess-hold-test"
        # Pre-record tokens to blow through standard patient grace limit (2,400)
        quota_manager.record_usage(session_id, 3000)

        result = run_clinical_agent(
            patient_id="P101",
            persona="patient",
            force_mock=True,
            role="patient_standard",
            session_id=session_id
        )
        assert result["quota_status"] == QuotaState.LIMIT_EXCEEDED.value
        assert "NOTICE: SESSION CONVERSATION LIMIT REACHED" in result["final_summary"]
        # In hold state, tools are bypassed to save costs
        assert "messages" in result
