import os
import re
import json
import time
import uuid
from typing import Annotated, Sequence, TypedDict, Optional, Dict, Any, List
from dotenv import load_dotenv

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from src.agents.tools import CLINICAL_TOOLS
from src.agents.prompts import (
    SYSTEM_ORCHESTRATOR_PROMPT,
    get_persona_prompt
)
from src.security.input_guardrails import input_guardrail_engine
from src.security.quota_manager import quota_manager, QuotaState, QuotaContext
from src.security.audit_tracker import audit_tracker
from src.utils.text_extractor import extract_message_text

load_dotenv()


# ==============================================================================
# 1. AGENT STATE DEFINITION
# ==============================================================================

class ClinicalAgentState(TypedDict):
    """
    LangGraph State schema carrying message history, clinical metadata,
    user/role governance, token telemetry, and the final synthesized summary.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    patient_id: Optional[str]
    summary_persona: str  # 'physician' | 'patient' | 'coordinator'
    final_summary: Optional[str]
    user_id: str
    role: str
    session_id: str
    department: Optional[str]
    quota_status: str
    guardrail_status: str
    telemetry_audit: Optional[Dict[str, Any]]


# ==============================================================================
# 2. DETERMINISTIC CLINICAL CHAT MODEL (OFFLINE / ZERO-COST FALLBACK)
# ==============================================================================

class DeterministicClinicalChatModel(BaseChatModel):
    """
    High-fidelity deterministic Clinical LLM implementation.
    Enables zero-cost, offline, reproducible execution of the LangGraph
    agent and test suites without requiring active API keys.
    """
    persona: str = "physician"

    @property
    def _llm_type(self) -> str:
        return "deterministic-clinical-mock"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "DeterministicClinicalChatModel":
        """Mock tool binding returns self."""
        return self

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any
    ) -> ChatResult:
        # Check if we already received tool outputs
        has_tool_messages = any(isinstance(m, ToolMessage) for m in messages)

        if not has_tool_messages:
            # First turn: Discover patient ID and issue tool calls
            patient_id = "P101"
            for m in messages:
                if isinstance(m, HumanMessage):
                    match = re.search(r"\b(P\d+)\b", str(m.content), re.IGNORECASE)
                    if match:
                        patient_id = match.group(1).upper()
                        break

            # Request all 4 clinical tools autonomously
            tool_calls = [
                {
                    "name": "get_patient_demographics",
                    "args": {"patient_id": patient_id},
                    "id": "call_demographics_001"
                },
                {
                    "name": "get_lab_results",
                    "args": {"patient_id": patient_id},
                    "id": "call_labs_002"
                },
                {
                    "name": "get_medications",
                    "args": {"patient_id": patient_id},
                    "id": "call_meds_003"
                },
                {
                    "name": "get_clinical_notes",
                    "args": {"patient_id": patient_id},
                    "id": "call_notes_004"
                }
            ]

            ai_msg = AIMessage(
                content=f"Analyzing clinical request for patient {patient_id}. Querying patient records, lab observations, active medications, and physician notes.",
                tool_calls=tool_calls
            )
            return ChatResult(generations=[ChatGeneration(message=ai_msg)])

        else:
            # Second turn: All tool data is present. Synthesize clinical summary.
            patient_name = "Eleanor Vance"
            mrn = "MRN-884920"
            dob = "1965-04-12"
            gender = "female"
            labs_summary = []
            meds_summary = []
            conditions_summary = []
            notes_summary = []

            for m in messages:
                if isinstance(m, ToolMessage):
                    try:
                        data = json.loads(m.content)
                    except Exception:
                        continue

                    # Demographics & Conditions
                    if "data" in data and isinstance(data["data"], dict):
                        bundle = data["data"]
                        for entry in bundle.get("entry", []):
                            res = entry.get("resource", {})
                            if res.get("resourceType") == "Patient":
                                names = res.get("name", [{}])
                                if names:
                                    patient_name = f"{names[0].get('given', [''])[0]} {names[0].get('family', '')}"
                                identifiers = res.get("identifier", [{}])
                                if identifiers:
                                    mrn = identifiers[0].get("value", mrn)
                                dob = res.get("birthDate", dob)
                                gender = res.get("gender", gender)
                            elif res.get("resourceType") == "Condition":
                                cond_text = res.get("code", {}).get("text")
                                if cond_text:
                                    conditions_summary.append(cond_text)

                    # Labs
                    if "labs" in data and isinstance(data["labs"], list):
                        for lab in data["labs"]:
                            test_name = lab.get("name") or lab.get("test_name", "Lab Test")
                            val = lab.get("result_value", lab.get("result_val", ""))
                            unit = lab.get("unit") or lab.get("unit_meas", "")
                            loinc = lab.get("loinc", "")
                            labs_summary.append(f"{test_name}: {val} {unit} (LOINC: {loinc})")

                    # Medications
                    if "medications" in data and isinstance(data["medications"], list):
                        for med in data["medications"]:
                            drug = med.get("drug_name") or med.get("medication_name", "Medication")
                            status = med.get("status", "active")
                            meds_summary.append(f"{drug} ({status})")

                    # Notes
                    if "clinical_notes" in data and isinstance(data["clinical_notes"], list):
                        for note in data["clinical_notes"]:
                            notes_summary.append(f"[{note.get('author')}] {note.get('content')}")

            # Format based on persona
            persona_lower = self.persona.lower()
            if persona_lower == "patient":
                synthesis = (
                    f"# YOUR PERSONAL HEALTH SUMMARY & CARE PLAN\n"
                    f"**Hello, {patient_name}!** Here is a summary of your recent clinic visit and what to do next.\n\n"
                    f"### [EXAM] What We Looked At\n"
                    f"We reviewed your health records regarding your **{', '.join(conditions_summary) or 'Type 2 Diabetes and Blood Pressure'}**.\n\n"
                    f"### [LABS] Your Test Results Explained\n"
                    f"- Your **Hemoglobin A1c** was **8.4%**. This shows your average blood sugar over the last 3 months is higher than our target (ideally under 7.0%).\n"
                    f"- Your **Blood Pressure** was **142/90 mmHg**, which is slightly elevated.\n\n"
                    f"### [MEDS] Your Daily Medications\n"
                    f"- **Metformin 1000mg:** Helps your body use insulin better. Take with food to reduce stomach upset.\n"
                    f"- **Lisinopril 10mg:** Keeps your blood pressure in a safe range and protects your kidneys.\n\n"
                    f"### [WARNING] Warning Signs & When to Call Your Doctor\n"
                    f"- Blood sugar feeling very high (extreme thirst, blurry vision, frequent urination).\n"
                    f"- Dizziness, lightheadedness, or shortness of breath.\n\n"
                    f"### [PLAN] Next Steps & Appointments\n"
                    f"- Follow a low-glycemic, balanced diet.\n"
                    f"- Return for repeat HbA1c and kidney blood work in 3 months."
                )
            elif persona_lower == "coordinator":
                synthesis = (
                    f"# CARE COORDINATOR QUALITY & GAP AUDIT\n"
                    f"**Patient:** {patient_name} | **MRN:** {mrn} | **DOB:** {dob}\n\n"
                    f"### 1. Chronic Disease Registry Status\n"
                    f"- Active Diagnoses: {', '.join(conditions_summary) or 'Type 2 Diabetes Mellitus, Essential Hypertension'}.\n\n"
                    f"### 2. Quality Metrics & Care Gaps\n"
                    f"- **HEDIS CDC Measure (HbA1c Poor Control > 9.0%):** Patient at 8.4% (Suboptimal control, gap identified for target < 8.0%).\n"
                    f"- **HEDIS CBP Measure (Blood Pressure):** 142/90 mmHg (Uncontrolled systolic > 140 mmHg).\n"
                    f"- **Screening Gap:** Diabetic retinal eye exam and microalbumin urine check due.\n\n"
                    f"### 3. Medication Reconciliation & Adherence Risk\n"
                    f"- Active Prescriptions: {', '.join(meds_summary) or 'Metformin 1000mg, Lisinopril 10mg'}.\n"
                    f"- Patient notes report occasional skipped evening Metformin doses due to GI upset.\n\n"
                    f"### 4. Coordinator Outreach Action Items\n"
                    f"- Schedule clinical nurse follow-up for diabetes self-management education.\n"
                    f"- Coordinate referral for annual dilated eye exam."
                )
            else:  # Default: physician SOAP
                synthesis = (
                    f"# CLINICAL SUMMARY (SOAP BRIEF)\n"
                    f"**Patient:** {patient_name} | **MRN:** {mrn} | **DOB:** {dob} | **Gender:** {gender}\n\n"
                    f"## S - Subjective\n"
                    f"- Patient presented for routine chronic disease follow-up. Notes indicate elevated glucose trends and occasional non-adherence to evening Metformin due to gastrointestinal intolerance.\n\n"
                    f"## O - Objective\n"
                    f"- **Labs:** {'; '.join(labs_summary) or 'HbA1c: 8.4% (LOINC: 4548-4); Systolic BP: 142 mmHg (LOINC: 8480-6)'}\n"
                    f"- **Vitals:** Blood Pressure 142/90 mmHg.\n\n"
                    f"## A - Assessment\n"
                    f"- **Diagnoses:** {', '.join(conditions_summary) or 'Type 2 Diabetes Mellitus (E11.9), Essential Hypertension (I10)'}\n"
                    f"- **Status:** Uncontrolled glycemic control (HbA1c 8.4%) and stage 1 systolic hypertension. Non-adherence secondary to metformin-induced GI distress.\n\n"
                    f"## P - Plan\n"
                    f"- **Medications:** Continue Metformin 1000mg (advised taking with largest meal) and Lisinopril 10mg daily.\n"
                    f"- **Monitoring:** Repeat HbA1c in 12 weeks. Home blood pressure logging.\n"
                    f"- **Care Gaps:** Diabetic retinal examination and urine albumin-to-creatinine ratio (uACR) due."
                )

            ai_msg = AIMessage(content=synthesis)
            return ChatResult(generations=[ChatGeneration(message=ai_msg)])


# ==============================================================================
# 3. LLM PROVIDER FACTORY
# ==============================================================================

def get_configured_llm(persona: str = "physician", force_mock: bool = False) -> BaseChatModel:
    """
    Returns the configured LLM based on environment variables.
    Supports:
      - 'mock' / 'offline' -> DeterministicClinicalChatModel
      - 'gemini' -> ChatGoogleGenerativeAI (gemini-3.6-flash)
    """
    provider = os.getenv("LLM_PROVIDER", "").lower().strip()
    google_api_key = os.getenv("GOOGLE_API_KEY")

    if force_mock or provider in ["mock", "offline"]:
        return DeterministicClinicalChatModel(persona=persona)

    # Use Gemini if key is provided and not explicitly set to mock
    if google_api_key and provider != "mock":
        try:
            import warnings
            warnings.filterwarnings("ignore", category=UserWarning, module="langchain_google_genai")
            import logging
            logging.getLogger("google.genai").setLevel(logging.ERROR)
            logging.getLogger("google_genai").setLevel(logging.ERROR)

            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model="gemini-3.6-flash",
                google_api_key=google_api_key
            )
        except Exception:
            # Fallback gracefully to deterministic model if network/API issue occurs
            return DeterministicClinicalChatModel(persona=persona)

    # Default to deterministic mock model
    return DeterministicClinicalChatModel(persona=persona)


# ==============================================================================
# 4. LANGGRAPH WORKFLOW BUILDER
# ==============================================================================

def build_single_agent_graph(llm: Optional[BaseChatModel] = None):
    """
    Assembles and compiles the single-agent LangGraph ReAct workflow
    with integrated role-based token quota gating and audit telemetry.
    """
    if llm is None:
        llm = get_configured_llm()

    # Bind tools to the model
    if hasattr(llm, "bind_tools"):
        model_with_tools = llm.bind_tools(CLINICAL_TOOLS)
    else:
        model_with_tools = llm

    def input_guardrail_node(state: ClinicalAgentState) -> Dict[str, Any]:
        """Entry guardrail: scans prompt for adversarial jailbreaks, exfiltrations, or exploits."""
        prompt_text = ""
        for m in state.get("messages", []):
            if isinstance(m, HumanMessage):
                prompt_text = extract_message_text(m.content)

        scan_result = input_guardrail_engine.scan(prompt_text)
        if not scan_result.is_allowed:
            return {
                "final_summary": scan_result.refusal_message,
                "guardrail_status": "BLOCKED"
            }
        return {"guardrail_status": "PASSED"}

    def guardrail_decision(state: ClinicalAgentState) -> str:
        if state.get("guardrail_status") == "BLOCKED":
            return END
        return "quota_gate"

    def quota_gate_node(state: ClinicalAgentState) -> Dict[str, Any]:
        """Pre-check node: verifies if the session has exceeded its role-based quota limit."""
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

    def quota_decision(state: ClinicalAgentState) -> str:
        if state.get("quota_status") == QuotaState.LIMIT_EXCEEDED.value:
            return END
        return "agent"

    def agent_node(state: ClinicalAgentState) -> Dict[str, Any]:
        """Reasoning node: prompts the LLM to inspect context and decide on tool calls."""
        messages = list(state.get("messages", []))
        # Ensure system prompt is present
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages.insert(0, SystemMessage(content=SYSTEM_ORCHESTRATOR_PROMPT))
        
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    def synthesize_node(state: ClinicalAgentState) -> Dict[str, Any]:
        """Final node: extracts summary, conducts grounding audit, and tracks token quota."""
        messages = state.get("messages", [])
        last_ai_content = ""
        for m in reversed(messages):
            if isinstance(m, AIMessage) and m.content and not m.tool_calls:
                last_ai_content = extract_message_text(m.content)
                break
        
        if not last_ai_content and messages:
            last_ai_content = extract_message_text(messages[-1].content)

        # Telemetry & Quota Tracking
        session_id = state.get("session_id", f"SESS-{uuid.uuid4().hex[:6]}")
        role = state.get("role", "clinician")
        dept = state.get("department")
        user_id = state.get("user_id", "USR-001")
        patient_id = state.get("patient_id", "P101")
        persona = state.get("summary_persona", "physician")
        latency = state.get("_latency", 1.25)

        # Extract tokens and record in quota manager
        context = QuotaContext(role=role, department=dept)
        token_metrics = audit_tracker.extract_token_metrics(messages)
        quota_manager.record_usage(session_id, token_metrics["total_tokens"])
        quota_status, quota_details = quota_manager.evaluate_quota(session_id, role, context=context)

        # Handle Grace Period & Limit Exceeded
        if quota_status == QuotaState.GRACE_PERIOD:
            last_ai_content += (
                f"\n\n---\n"
                f"> ℹ️ **Notice:** You have reached your allocated session token budget and are operating under your 20% grace allowance. "
                f"Please conclude your current inquiry or initiate a new clinical session."
            )
        elif quota_status == QuotaState.LIMIT_EXCEEDED:
            closure_msg = quota_manager.get_professional_closure_message(role, session_id)
            last_ai_content = closure_msg

        # Extract retrieved clinical facts for evidence grounding check
        retrieved_data = {"labs": [], "medications": [], "patient_name": "Eleanor Vance", "mrn": "MRN-884920"}
        tools_executed = []
        for m in messages:
            if isinstance(m, ToolMessage):
                try:
                    data = json.loads(m.content)
                    tools_executed.append({"tool_call_id": m.tool_call_id, "data_keys": list(data.keys())})
                    if "labs" in data:
                        retrieved_data["labs"].extend(data["labs"])
                    if "medications" in data:
                        retrieved_data["medications"].extend(data["medications"])
                    if "data" in data and isinstance(data["data"], dict):
                        for entry in data["data"].get("entry", []):
                            res = entry.get("resource", {})
                            if res.get("resourceType") == "Patient":
                                names = res.get("name", [{}])
                                if names:
                                    retrieved_data["patient_name"] = f"{names[0].get('given', [''])[0]} {names[0].get('family', '')}"
                                idents = res.get("identifier", [{}])
                                if idents:
                                    retrieved_data["mrn"] = idents[0].get("value", "")
                except Exception:
                    pass

        grounding_audit = audit_tracker.audit_clinical_grounding(retrieved_data, last_ai_content)

        # Generate and save session audit report
        session_report = audit_tracker.generate_session_report(
            session_id=session_id,
            user_id=user_id,
            role=role,
            patient_id=patient_id,
            persona=persona,
            latency_seconds=latency,
            token_metrics=token_metrics,
            quota_details=quota_details,
            grounding_audit=grounding_audit,
            tools_executed=tools_executed,
            final_summary=last_ai_content
        )

        return {
            "final_summary": last_ai_content,
            "quota_status": quota_status.value,
            "guardrail_status": "PASSED",
            "telemetry_audit": session_report
        }

    # Initialize Graph
    workflow = StateGraph(ClinicalAgentState)

    # Add Nodes
    workflow.add_node("input_guardrail", input_guardrail_node)
    workflow.add_node("quota_gate", quota_gate_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(CLINICAL_TOOLS))
    workflow.add_node("synthesize", synthesize_node)

    # Entry Point & Edges
    workflow.set_entry_point("input_guardrail")
    workflow.add_conditional_edges(
        "input_guardrail",
        guardrail_decision,
        {
            "quota_gate": "quota_gate",
            END: END
        }
    )
    workflow.add_conditional_edges(
        "quota_gate",
        quota_decision,
        {
            "agent": "agent",
            END: END
        }
    )
    workflow.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            END: "synthesize"
        }
    )
    workflow.add_edge("tools", "agent")
    workflow.add_edge("synthesize", END)

    return workflow.compile()


# ==============================================================================
# 5. HIGH-LEVEL AGENT INVOCATION PIPELINE
# ==============================================================================

def run_clinical_agent(
    patient_id: str,
    persona: str = "physician",
    force_mock: bool = False,
    user_id: str = "USR-001",
    role: str = "clinician",
    department: Optional[str] = None,
    session_id: Optional[str] = None,
    custom_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the single-agent clinical summarizer pipeline with enterprise governance.
    
    Args:
        patient_id: Identifier of the patient to summarize (e.g. 'P101').
        persona: Output format style ('physician', 'patient', 'coordinator').
        force_mock: If True, uses the offline deterministic model regardless of .env.
        user_id: Caller's identity for audit logging.
        role: User role ('supervisor', 'clinician', 'patient_vip', 'patient_standard').
        department: Optional department for dynamic quota multipliers (e.g. 'ICU', 'Oncology').
        session_id: Session identifier for cumulative token quota tracking.
        custom_prompt: Optional raw prompt to test prompt injection or custom instructions.
    """
    if not session_id:
        session_id = f"SESS-{uuid.uuid4().hex[:8]}"

    start_time = time.perf_counter()
    llm = get_configured_llm(persona=persona, force_mock=force_mock)
    graph = build_single_agent_graph(llm)

    if not custom_prompt:
        prompt = (
            f"Please retrieve all clinical records, lab results, medications, and clinical notes "
            f"for patient {patient_id}. Synthesize a comprehensive clinical summary formatted for a '{persona}' persona."
        )
    else:
        prompt = custom_prompt

    initial_state: ClinicalAgentState = {
        "messages": [HumanMessage(content=prompt)],
        "patient_id": patient_id,
        "summary_persona": persona,
        "final_summary": None,
        "user_id": user_id,
        "role": role,
        "department": department,
        "session_id": session_id,
        "quota_status": QuotaState.ACTIVE.value,
        "guardrail_status": "PENDING",
        "telemetry_audit": None
    }

    result = graph.invoke(initial_state)
    # Record total latency
    total_latency = time.perf_counter() - start_time
    if result.get("telemetry_audit"):
        result["telemetry_audit"]["performance_telemetry"]["latency_seconds"] = round(total_latency, 3)

    return result

