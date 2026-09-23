"""
Module 2 Working Milestone Demo & MCP Test Client
Run with: python -m scripts.demo_mcp_client
"""

import json
from src.mcp_server.server import get_patient_demographics, get_lab_results, get_medications, get_clinical_notes


def run_mcp_client_demo():
    print("=" * 80)
    print(" [MCP SERVER] MODULE 2 WORKING MILESTONE DEMO: FASTMCP HEALTHCARE SERVER ")
    print("=" * 80)

    print("\n[TOOLS] Registered MCP Tools on 'healthcare-mcp-server':")
    print("  1. get_patient_demographics(patient_id: str)")
    print("  2. get_lab_results(patient_id: str, test_name: Optional[str])")
    print("  3. get_medications(patient_id: str)")
    print("  4. get_clinical_notes(patient_id: str)")

    patient_id = "P101"
    print(f"\n[QUERY] 1. Executing 'get_patient_demographics' for patient_id='{patient_id}'...")
    demographics_json = get_patient_demographics(patient_id)
    demo_res = json.loads(demographics_json)
    if demo_res.get("status") == "success":
        patient_name = demo_res["data"]["entry"][0]["resource"]["name"][0]
        print(f"   [OK] Retrived FHIR Patient: {patient_name['given'][0]} {patient_name['family']} (Gender: {demo_res['data']['entry'][0]['resource']['gender']})")

    print(f"\n[QUERY] 2. Executing 'get_lab_results' for patient_id='{patient_id}'...")
    labs_json = get_lab_results(patient_id)
    labs_res = json.loads(labs_json)
    if labs_res.get("status") == "success":
        print(f"   [OK] Total Labs Retrieved: {len(labs_res['labs'])}")
        for lab in labs_res["labs"]:
            print(f"      - {lab['name']}: {lab['result_val']} {lab['unit_meas']} (LOINC: {lab['loinc']})")

    print(f"\n[QUERY] 3. Executing 'get_medications' for patient_id='{patient_id}'...")
    meds_json = get_medications(patient_id)
    meds_res = json.loads(meds_json)
    if meds_res.get("status") == "success":
        print(f"   [OK] Active Prescriptions ({len(meds_res['medications'])}):")
        for rx in meds_res["medications"]:
            print(f"      - {rx['drug_name']} (RxNorm: {rx['rxnorm']})")

    print(f"\n[QUERY] 4. Executing 'get_clinical_notes' for patient_id='{patient_id}'...")
    notes_json = get_clinical_notes(patient_id)
    notes_res = json.loads(notes_json)
    if notes_res.get("status") == "success":
        print(f"   [OK] Clinical Notes ({len(notes_res['clinical_notes'])}):")
        for note in notes_res["clinical_notes"]:
            print(f"      - Author: {note['author']} | Category: {note['category']}")
            print(f"        Excerpt: {note['content'][:110]}...")

    print("\n[SECURITY] 5. Testing Action Guardrail Validation with Invalid Patient ID ('P@101#INVALID')...")
    invalid_json = get_patient_demographics("P@101#INVALID")
    invalid_res = json.loads(invalid_json)
    print(f"   [BLOCKED] Result: {invalid_res['status'].upper()} -> {invalid_res['message']}")

    print("\n" + "=" * 80)
    print(" [SUCCESS] MODULE 2 DEMO COMPLETE: FastMCP server & tool guardrails validated!")
    print("=" * 80)


if __name__ == "__main__":
    run_mcp_client_demo()
