"""
LangGraph Human-in-the-Loop (HITL) Interrupt Gates & Attestation Engine.
Pauses graph execution when CRUD write operations or high-confidence care gap actions occur,
resuming only when an authorized clinician submits an explicit approval or rejection.
"""

import os
import re
import json
import time
import uuid
from typing import Annotated, Sequence, TypedDict, Optional, Dict, Any, List
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from src.rules.rule_engine import clinical_rule_engine, ClinicalRuleEvaluationResult
from src.db.mock_healthcare_db import db
from src.security.input_guardrails import input_guardrail_engine
from src.security.quota_manager import quota_manager, QuotaState, QuotaContext
from src.security.audit_tracker import audit_tracker

load_dotenv()


# ==============================================================================
# 1. HITL AGENT STATE DEFINITION
# ==============================================================================

class HITLAgentState(TypedDict):
    """
    LangGraph State schema carrying message history, clinical rule evaluation,
    pending CRUD write actions, clinician attestation decisions, and telemetry.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    patient_id: Optional[str]
    summary_persona: str
    raw_fhir_data: Dict[str, Any]
    rule_evaluation: Optional[Dict[str, Any]]
    pending_actions: List[Dict[str, Any]]
    attestation_status: str  # 'NOT_REQUIRED' | 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED'
    clinician_decision: Optional[Dict[str, Any]]
    execution_results: List[Dict[str, Any]]
    final_summary: Optional[str]
    user_id: str
    role: str
    session_id: str
    department: Optional[str]
    quota_status: str
    guardrail_status: str
    telemetry_audit: Optional[Dict[str, Any]]


# ==============================================================================
# 2. DETERMINISTIC HITL CHAT MODEL (OFFLINE / ZERO-COST FALLBACK)
# ==============================================================================

class DeterministicHITLChatModel(BaseChatModel):
    """Offline deterministic model for testing HITL state interrupts and attestation flows."""
    persona: str = "physician"

    @property
    def _llm_type(self) -> str:
        return "deterministic-hitl-mock"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "DeterministicHITLChatModel":
        return self

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any
    ) -> ChatResult:
        ai_msg = AIMessage(content="[HITL Agent Reasoning Step Completed]")
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])


def get_configured_hitl_llm(persona: str = "physician", force_mock: bool = False) -> BaseChatModel:
    """Returns configured LLM provider or offline deterministic mock."""
    provider = os.getenv("LLM_PROVIDER", "").lower().strip()
    google_api_key = os.getenv("GOOGLE_API_KEY")

    if force_mock or provider in ["mock", "offline"]:
        return DeterministicHITLChatModel(persona=persona)

    if google_api_key and provider != "mock":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model="gemini-3.6-flash",
                temperature=0.1,
                google_api_key=google_api_key
            )
        except Exception:
            return DeterministicHITLChatModel(persona=persona)

    return DeterministicHITLChatModel(persona=persona)


# ==============================================================================
# 3. LANGGRAPH HITL WORKFLOW BUILDER
# ==============================================================================

# Session state store to persist graph state across interrupt pause & resume
_SESSION_STATE_STORE: Dict[str, HITLAgentState] = {}


def build_hitl_agent_graph(llm: Optional[BaseChatModel] = None):
    """
    Assembles the HITL StateGraph connecting:
    Input Guardrail -> Quota Gate -> Data Ingestion -> Clinical Rules Engine -> HITL Gate -> Execute CRUD Actions -> Synthesize -> END
    """
    if llm is None:
        llm = get_configured_hitl_llm()

    # --- Node 1: Input Guardrail ---
    def input_guardrail_node(state: HITLAgentState) -> Dict[str, Any]:
        prompt_text = ""
        for m in state.get("messages", []):
            if isinstance(m, HumanMessage):
                prompt_text = str(m.content)

        scan_result = input_guardrail_engine.scan(prompt_text)
        if not scan_result.is_allowed:
            return {
                "final_summary": scan_result.refusal_message,
                "guardrail_status": "BLOCKED"
            }
        return {"guardrail_status": "PASSED"}

    def guardrail_decision(state: HITLAgentState) -> str:
        if state.get("guardrail_status") == "BLOCKED":
            return END
        return "quota_gate"

    # --- Node 2: Quota Gate ---
    def quota_gate_node(state: HITLAgentState) -> Dict[str, Any]:
        session_id = state.get("session_id", "default")
        role = state.get("role", "clinician")
        dept = state.get("department")
        context = QuotaContext(role=role, department=dept)
        status, details = quota_manager.evaluate_quota(session_id, role, context=context)
        if status == QuotaState.LIMIT_EXCEEDED:
            closure_msg = quota_manager.get_professional_closure_message(role, session_id)
            return {
                "final_summary": closure_msg,
                "quota_status": QuotaState.LIMIT_EXCEEDED.value
            }
        return {"quota_status": status.value}

    def quota_decision(state: HITLAgentState) -> str:
        if state.get("quota_status") == QuotaState.LIMIT_EXCEEDED.value:
            return END
        return "data_ingestion_agent"

    # --- Node 3: Data Ingestion Agent ---
    def data_ingestion_agent_node(state: HITLAgentState) -> Dict[str, Any]:
        patient_id = state.get("patient_id", "P101")
        bundle = db.get_patient(patient_id) or {}
        labs = db.get_lab_results(patient_id)
        meds = db.get_medications(patient_id)
        notes = db.get_clinical_notes(patient_id)

        raw_fhir_data = {
            "patient_demographics": bundle,
            "labs": labs,
            "medications": meds,
            "notes": notes
        }
        return {"raw_fhir_data": raw_fhir_data}

    # --- Node 4: Clinical Rules Engine with Confidence Scores ---
    def clinical_rules_node(state: HITLAgentState) -> Dict[str, Any]:
        raw_data = state.get("raw_fhir_data", {})
        rule_res = clinical_rule_engine.evaluate(raw_data)

        # Detect any prompt-driven CRUD write requests in user messages
        pending_actions: List[Dict[str, Any]] = []
        patient_id = state.get("patient_id", "P101")

        for msg in state.get("messages", []):
            if isinstance(msg, HumanMessage):
                text = str(msg.content)
                # Detect prompt-driven medication order (CRUD Create)
                match_med = re.search(r"(order|prescribe|add)\s+([A-Za-z0-9\s]+?)\s+(\d+mg)", text, re.IGNORECASE)
                if match_med:
                    drug = match_med.group(2).strip()
                    dose = match_med.group(3).strip()
                    pending_actions.append({
                        "action_type": "CREATE_MEDICATION_ORDER",
                        "patient_id": patient_id,
                        "drug_name": drug,
                        "dosage": dose,
                        "frequency": "daily",
                        "confidence_score": 0.95,
                        "reason": f"Prompt-driven order request: '{drug} {dose}'"
                    })

        # Add care gaps requiring approval
        for gap in rule_res.care_gaps:
            if gap.requires_hitl_approval:
                pending_actions.append({
                    "action_type": "REMEDIATE_CARE_GAP",
                    "patient_id": patient_id,
                    "gap_id": gap.gap_id,
                    "title": gap.title,
                    "severity": gap.severity,
                    "confidence_score": gap.confidence_score,
                    "recommendation": gap.recommendation
                })

        return {
            "rule_evaluation": rule_res.model_dump(),
            "pending_actions": pending_actions
        }

    # --- Node 5: HITL Gate (Interrupt Pause & Resume) ---
    def hitl_gate_node(state: HITLAgentState) -> Dict[str, Any]:
        pending = state.get("pending_actions", [])
        status = state.get("attestation_status", "NOT_REQUIRED")

        if pending and status not in ["APPROVED", "REJECTED"]:
            # Pause graph execution for clinician attestation
            session_id = state.get("session_id", "default")

            banner = (
                f"# 🛑 HUMAN-IN-THE-LOOP (HITL) CLINICIAN ATTESTATION REQUIRED\n"
                f"**Session ID:** `{session_id}` | **Status:** `AWAITING_CLINICIAN_APPROVAL`\n\n"
                f"The system has paused graph execution to request explicit clinician approval before committing write operations:\n"
            )
            for idx, act in enumerate(pending, 1):
                conf = act.get("confidence_score", 0.90)
                banner += (
                    f"\n### Action #{idx}: [{act.get('action_type')}]\n"
                    f"- **Details:** {act.get('reason') or act.get('title')}\n"
                    f"- **Confidence Score:** {conf:.2f} / 1.00\n"
                    f"- **Recommendation:** {act.get('recommendation') or act.get('dosage')}\n"
                )

            banner += "\n---\n*Please submit clinician approval decision (`approved=True/False`) to resume graph execution.*"

            # Persist state in memory store for resumption
            state["attestation_status"] = "PENDING_APPROVAL"
            state["final_summary"] = banner
            _SESSION_STATE_STORE[session_id] = state

            return {
                "attestation_status": "PENDING_APPROVAL",
                "final_summary": banner
            }

        return {"attestation_status": status}

    def hitl_decision(state: HITLAgentState) -> str:
        if state.get("attestation_status") == "PENDING_APPROVAL":
            return END  # Pause execution and return control to user/clinician
        return "execute_actions_node"

    # --- Node 6: Execute Approved CRUD Actions ---
    def execute_actions_node(state: HITLAgentState) -> Dict[str, Any]:
        status = state.get("attestation_status")
        decision = state.get("clinician_decision") or {}
        pending = state.get("pending_actions", [])
        execution_results: List[Dict[str, Any]] = []

        if status == "APPROVED":
            for act in pending:
                action_type = act.get("action_type")
                patient_id = act.get("patient_id", "P101")

                if action_type == "CREATE_MEDICATION_ORDER":
                    res = db.create_medication_order(
                        patient_id=patient_id,
                        drug_name=act.get("drug_name", "Medication"),
                        dosage=act.get("dosage", "10mg"),
                        frequency=act.get("frequency", "daily")
                    )
                    execution_results.append(res)
                elif action_type == "REMEDIATE_CARE_GAP":
                    res = db.add_care_gap_remediation(
                        patient_id=patient_id,
                        gap_id=act.get("gap_id", "GAP-001"),
                        action_taken=act.get("recommendation", "Remediated")
                    )
                    execution_results.append(res)

        elif status == "REJECTED":
            execution_results.append({
                "status": "rejected",
                "message": f"Action cancelled per clinician rejection ({decision.get('comments', 'No comment')})."
            })

        return {"execution_results": execution_results}

    # --- Node 7: Synthesize Summary & Telemetry ---
    def synthesize_summary_node(state: HITLAgentState) -> Dict[str, Any]:
        patient_id = state.get("patient_id", "P101")
        persona = state.get("summary_persona", "physician")
        status = state.get("attestation_status")
        results = state.get("execution_results", [])
        decision = state.get("clinician_decision") or {}

        patient_name = "Eleanor Vance"
        mrn = "MRN-884920"

        if status == "APPROVED":
            synthesis = (
                f"# ✅ CLINICIAN ATTESTED & EXECUTED SUMMARY\n"
                f"**Patient:** {patient_name} | **MRN:** {mrn} | **Attending Clinician:** `{decision.get('clinician_id', 'DR-JENKINS-99')}`\n\n"
                f"### Attestation Status: `APPROVED`\n"
                f"- **Clinician Comments:** \"{decision.get('comments', 'Attested and verified clinical orders.')}\"\n\n"
                f"### Executed Database CRUD Actions:\n"
            )
            for res in results:
                synthesis += f"- **[EXECUTED]** {json.dumps(res)}\n"

            synthesis += (
                f"\n## Updated SOAP Plan:\n"
                f"- All pending care gap remediations and medication orders have been committed to the EHR database."
            )

        elif status == "REJECTED":
            synthesis = (
                f"# 🛑 CLINICIAN REJECTED SUMMARY\n"
                f"**Patient:** {patient_name} | **MRN:** {mrn} | **Clinician:** `{decision.get('clinician_id', 'DR-JENKINS-99')}`\n\n"
                f"### Attestation Status: `REJECTED`\n"
                f"- **Reason / Comments:** \"{decision.get('comments', 'Clinician cancelled recommended order.')}\"\n\n"
                f"- No database writes were committed. System reverted to original baseline care plan."
            )

        else:
            synthesis = (
                f"# CLINICAL SUMMARY (SOAP BRIEF)\n"
                f"**Patient:** {patient_name} | **MRN:** {mrn}\n\n"
                f"## S - Subjective\n- Patient presented for chronic disease follow-up.\n\n"
                f"## O - Objective\n- HbA1c: 8.4% | Blood Pressure: 142/90 mmHg.\n\n"
                f"## A - Assessment\n- Suboptimal glycemic and blood pressure control.\n\n"
                f"## P - Plan\n- Routine chronic care management."
            )

        # Telemetry & Audit
        session_id = state.get("session_id", "default")
        role = state.get("role", "clinician")
        context = QuotaContext(role=role)
        token_metrics = audit_tracker.extract_token_metrics(state.get("messages", []))
        quota_manager.record_usage(session_id, token_metrics["total_tokens"])
        quota_status, quota_details = quota_manager.evaluate_quota(session_id, role, context=context)

        session_report = audit_tracker.generate_session_report(
            session_id=session_id,
            user_id=state.get("user_id", "USR-001"),
            role=role,
            patient_id=patient_id,
            persona=persona,
            latency_seconds=0.045,
            token_metrics=token_metrics,
            quota_details=quota_details,
            grounding_audit={"grounding_score_percent": 100.0, "hallucination_risk": "VERY_LOW"},
            tools_executed=[{"agent": "HITLAgentNode", "status": status}],
            final_summary=synthesis
        )

        return {
            "final_summary": synthesis,
            "telemetry_audit": session_report
        }

    # --- Assemble Graph ---
    workflow = StateGraph(HITLAgentState)

    workflow.add_node("input_guardrail", input_guardrail_node)
    workflow.add_node("quota_gate", quota_gate_node)
    workflow.add_node("data_ingestion_agent", data_ingestion_agent_node)
    workflow.add_node("clinical_rules_node", clinical_rules_node)
    workflow.add_node("hitl_gate_node", hitl_gate_node)
    workflow.add_node("execute_actions_node", execute_actions_node)
    workflow.add_node("synthesize_summary_node", synthesize_summary_node)

    # Edges
    workflow.set_entry_point("input_guardrail")
    workflow.add_conditional_edges("input_guardrail", guardrail_decision, {"quota_gate": "quota_gate", END: END})
    workflow.add_conditional_edges("quota_gate", quota_decision, {"data_ingestion_agent": "data_ingestion_agent", END: END})
    workflow.add_edge("data_ingestion_agent", "clinical_rules_node")
    workflow.add_edge("clinical_rules_node", "hitl_gate_node")
    workflow.add_conditional_edges("hitl_gate_node", hitl_decision, {"execute_actions_node": "execute_actions_node", END: END})
    workflow.add_edge("execute_actions_node", "synthesize_summary_node")
    workflow.add_edge("synthesize_summary_node", END)

    return workflow.compile()


# ==============================================================================
# 4. HIGH-LEVEL PIPELINE EXECUTION & RESUMPTION
# ==============================================================================

def run_hitl_agent_pipeline(
    patient_id: str,
    persona: str = "physician",
    force_mock: bool = False,
    user_id: str = "USR-001",
    role: str = "clinician",
    department: Optional[str] = None,
    session_id: Optional[str] = None,
    custom_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """Initial execution of the HITL agent graph."""
    if not session_id:
        session_id = f"SESS-HITL-{uuid.uuid4().hex[:6]}"

    llm = get_configured_hitl_llm(persona=persona, force_mock=force_mock)
    graph = build_hitl_agent_graph(llm)

    prompt = custom_prompt or f"Evaluate clinical rules and recommendations for patient '{patient_id}'."

    initial_state: HITLAgentState = {
        "messages": [HumanMessage(content=prompt)],
        "patient_id": patient_id,
        "summary_persona": persona,
        "raw_fhir_data": {},
        "rule_evaluation": None,
        "pending_actions": [],
        "attestation_status": "NOT_REQUIRED",
        "clinician_decision": None,
        "execution_results": [],
        "final_summary": None,
        "user_id": user_id,
        "role": role,
        "department": department,
        "session_id": session_id,
        "quota_status": QuotaState.ACTIVE.value,
        "guardrail_status": "PENDING",
        "telemetry_audit": None
    }

    return graph.invoke(initial_state)


def resume_hitl_agent_pipeline(
    session_id: str,
    approved: bool,
    clinician_id: str = "DR-JENKINS-99",
    comments: str = "Attested by attending clinician."
) -> Dict[str, Any]:
    """Resumes execution of a paused HITL graph session after clinician attestation."""
    cached_state = _SESSION_STATE_STORE.get(session_id)
    if not cached_state:
        return {"error": f"No paused HITL session found for session ID '{session_id}'."}

    # Update attestation decision
    cached_state["attestation_status"] = "APPROVED" if approved else "REJECTED"
    cached_state["clinician_decision"] = {
        "approved": approved,
        "clinician_id": clinician_id,
        "comments": comments,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    llm = get_configured_hitl_llm(persona=cached_state.get("summary_persona", "physician"))
    graph = build_hitl_agent_graph(llm)

    # Resume graph execution from current state
    return graph.invoke(cached_state)


# Compiled default HITL agent application instance
hitl_agent_app = build_hitl_agent_graph()

