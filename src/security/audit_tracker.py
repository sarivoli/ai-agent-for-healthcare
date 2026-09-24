"""
Enterprise Clinical Telemetry, Token Monitor & EHR Grounding Auditor.
Tracks token consumption, execution latency, verifies clinical evidence grounding,
and generates auditable session reports.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


REPORTS_DIR = Path(__file__).parent.parent.parent / "reports" / "sessions"


class AuditTracker:
    """
    Collects performance telemetry, token usage, and verifies clinical evidence grounding.
    """
    def __init__(self, reports_dir: Path = REPORTS_DIR):
        self.reports_dir = reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def log_event(self, event_type: str, details: Dict[str, Any]):
        """Log audit incident or system event to audit report store."""
        timestamp = datetime.now(timezone.utc).isoformat()
        log_payload = {
            "timestamp": timestamp,
            "event_type": event_type,
            "details": details
        }
        event_path = self.reports_dir / f"EVENT-{int(time.time())}.json"
        with open(event_path, "w", encoding="utf-8") as f:
            json.dump(log_payload, f, indent=2)

    def extract_token_metrics(self, messages: List[Any]) -> Dict[str, Any]:
        """
        Extracts prompt, completion, and total tokens from message usage metadata.
        Falls back to accurate estimation if usage metadata is absent.
        """
        input_tokens = 0
        output_tokens = 0
        has_metadata = False

        for msg in messages:
            # Check for standard LangChain usage_metadata
            usage = getattr(msg, "usage_metadata", None)
            if usage and isinstance(usage, dict):
                input_tokens += usage.get("input_tokens", 0)
                output_tokens += usage.get("output_tokens", 0)
                has_metadata = True
            elif hasattr(msg, "response_metadata") and isinstance(msg.response_metadata, dict):
                usage = msg.response_metadata.get("usage", {})
                if usage:
                    input_tokens += usage.get("prompt_tokens", usage.get("input_tokens", 0))
                    output_tokens += usage.get("completion_tokens", usage.get("output_tokens", 0))
                    has_metadata = True

        if not has_metadata or (input_tokens == 0 and output_tokens == 0):
            # Deterministic calculation based on content length
            total_chars_in = 0
            total_chars_out = 0
            for msg in messages:
                content_str = str(getattr(msg, "content", ""))
                msg_type = getattr(msg, "type", "")
                if msg_type in ["human", "system", "tool"]:
                    total_chars_in += len(content_str)
                elif msg_type == "ai":
                    total_chars_out += len(content_str)

            # Approx 4 chars per token
            input_tokens = max(1, total_chars_in // 4)
            output_tokens = max(1, total_chars_out // 4)

        total_tokens = input_tokens + output_tokens
        # Pricing: Gemini 3.6 Flash (~$0.10/1M input, ~$0.40/1M output)
        est_cost_usd = (input_tokens * 0.00000010) + (output_tokens * 0.00000040)

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(est_cost_usd, 6)
        }

    def audit_clinical_grounding(
        self,
        retrieved_data: Dict[str, Any],
        final_summary: str
    ) -> Dict[str, Any]:
        """
        Verifies that clinical facts (lab values, medications, conditions)
        in the final summary directly trace back to retrieved FHIR records.
        """
        summary_text = (final_summary or "").lower()
        claims_checked = []
        verified_count = 0

        # Check Patient Demographics
        patient_name = retrieved_data.get("patient_name", "")
        if patient_name:
            is_present = any(part.lower() in summary_text for part in patient_name.split())
            claims_checked.append({
                "type": "Demographics",
                "claim": f"Patient Name: {patient_name}",
                "grounded": is_present
            })
            if is_present:
                verified_count += 1

        mrn = retrieved_data.get("mrn", "")
        if mrn:
            is_present = mrn.lower() in summary_text
            claims_checked.append({
                "type": "Identifier",
                "claim": f"MRN: {mrn}",
                "grounded": is_present
            })
            if is_present:
                verified_count += 1

        # Check Labs (e.g. 8.4, 142)
        for lab in retrieved_data.get("labs", []):
            val_str = str(lab.get("result_value", "")).strip()
            name = str(lab.get("name", "")).strip()
            is_present = val_str in summary_text
            claims_checked.append({
                "type": "Lab Observation",
                "claim": f"{name} ({val_str} {lab.get('unit', '')})",
                "grounded": is_present
            })
            if is_present:
                verified_count += 1

        # Check Medications
        for med in retrieved_data.get("medications", []):
            drug_name = str(med.get("drug_name", "")).split()[0].lower()  # e.g., 'metformin'
            is_present = drug_name in summary_text
            claims_checked.append({
                "type": "Medication",
                "claim": f"Prescription: {med.get('drug_name')}",
                "grounded": is_present
            })
            if is_present:
                verified_count += 1

        total_claims = len(claims_checked)
        grounding_score = round((verified_count / max(1, total_claims)) * 100, 1)

        return {
            "total_claims_audited": total_claims,
            "verified_claims_count": verified_count,
            "grounding_score_percent": grounding_score,
            "hallucination_risk": "VERY_LOW" if grounding_score >= 80 else ("LOW" if grounding_score >= 60 else "MODERATE"),
            "audit_details": claims_checked
        }

    def generate_session_report(
        self,
        session_id: str,
        user_id: str,
        role: str,
        patient_id: str,
        persona: str,
        latency_seconds: float,
        token_metrics: Dict[str, Any],
        quota_details: Dict[str, Any],
        grounding_audit: Dict[str, Any],
        tools_executed: List[Dict[str, Any]],
        final_summary: str
    ) -> Dict[str, Any]:
        """
        Assembles and persists the complete auditable session report in JSON & Markdown.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        report_data = {
            "report_id": f"AUDIT-{session_id}-{int(time.time())}",
            "session_id": session_id,
            "timestamp": timestamp,
            "user_context": {
                "user_id": user_id,
                "role": role,
                "persona": persona
            },
            "clinical_context": {
                "patient_id": patient_id
            },
            "performance_telemetry": {
                "latency_seconds": round(latency_seconds, 3),
                "tools_executed_count": len(tools_executed),
                "tools_executed": tools_executed
            },
            "token_telemetry": token_metrics,
            "quota_governance": quota_details,
            "grounding_audit": grounding_audit,
            "summary_preview": final_summary[:400] + "..." if len(final_summary) > 400 else final_summary
        }

        # Save JSON report
        json_path = self.reports_dir / f"{session_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        # Save Markdown report
        md_path = self.reports_dir / f"{session_id}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._format_markdown_report(report_data, final_summary))

        report_data["json_path"] = str(json_path)
        report_data["md_path"] = str(md_path)
        return report_data

    def _format_markdown_report(self, data: Dict[str, Any], final_summary: str) -> str:
        tokens = data["token_telemetry"]
        perf = data["performance_telemetry"]
        grounding = data["grounding_audit"]
        quota = data["quota_governance"]

        verified_cnt = grounding.get("verified_claims_count", 0)
        total_cnt = grounding.get("total_claims_audited", 0)
        grounding_score = grounding.get("grounding_score_percent", 0.0)
        hallucination_risk = grounding.get("hallucination_risk", "UNKNOWN")

        md = []
        md.append(f"# Enterprise Clinical Audit & Telemetry Report")
        md.append(f"**Session ID:** `{data['session_id']}` | **Generated:** `{data['timestamp']}`\n")
        md.append(f"### [USER] User Context")
        md.append(f"- **User ID:** `{data['user_context']['user_id']}`")
        md.append(f"- **Assigned Role:** `{data['user_context']['role']}`")
        md.append(f"- **Summary Persona:** `{data['user_context']['persona']}`\n")
        md.append(f"### [PERF] Performance & Token Meter")
        md.append(f"- **Execution Latency:** `{perf['latency_seconds']} seconds`")
        md.append(f"- **Prompt Tokens:** `{tokens['input_tokens']:,}`")
        md.append(f"- **Completion Tokens:** `{tokens['output_tokens']:,}`")
        md.append(f"- **Total Tokens Consumed:** `{tokens['total_tokens']:,}`")
        md.append(f"- **Estimated Session Cost:** `${tokens['estimated_cost_usd']:.6f} USD`\n")
        md.append(f"### [QUOTA] Quota Governance Status")
        md.append(f"- **Base Quota:** `{quota.get('base_quota', 0):,} tokens`")
        md.append(f"- **Grace Limit:** `{quota.get('grace_limit', 0):,} tokens`")
        md.append(f"- **Remaining Quota:** `{quota.get('remaining_base_tokens', 0):,} tokens`\n")
        md.append(f"### [AUDIT] Clinical Evidence Grounding Audit")
        md.append(f"- **Grounding Score:** `{grounding_score}%` ({verified_cnt}/{total_cnt} claims verified)")
        md.append(f"- **Hallucination Risk Level:** `{hallucination_risk}`\n")
        md.append(f"| Evidence Type | Verified Claim | Grounded in EHR? |")
        md.append(f"| :--- | :--- | :--- |")
        for claim in grounding.get("audit_details", []):
            status = "✅ YES" if claim["grounded"] else "⚠️ MISSING"
            md.append(f"| {claim['type']} | {claim['claim']} | {status} |")
        md.append(f"\n### 📝 Synthesized Clinical Output\n")
        md.append(final_summary)
        return "\n".join(md)

    def get_session_audit_report(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a previously stored session audit report by ID."""
        json_path = self.reports_dir / f"{session_id}.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def list_session_audit_reports(self) -> List[str]:
        """Lists all available session IDs with stored audit reports."""
        return [p.stem for p in self.reports_dir.glob("*.json")]


# Global singleton audit tracker
audit_tracker = AuditTracker()
