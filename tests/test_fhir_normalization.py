"""
Module 1 Working Milestone Demo & Test Suite: FHIR Normalization
Run with: python -m tests.test_fhir_normalization  OR  pytest tests/test_fhir_normalization.py
"""

import json
from pathlib import Path
from src.fhir.normalizer import normalize_vendor_patient
from src.fhir.schemas import FHIRBundle, FHIRPatient, FHIRObservation, FHIRCondition, FHIRMedicationRequest, FHIREncounter


def test_fhir_normalization_pipeline():
    """Validates raw vendor data normalization to FHIR R4 Bundle."""
    mock_data_path = Path(__file__).parent.parent / "src" / "fhir" / "mock_vendor_data.json"
    assert mock_data_path.exists(), f"Mock vendor data file missing at {mock_data_path}"

    with open(mock_data_path, "r", encoding="utf-8") as f:
        vendor_records = json.load(f)

    assert len(vendor_records) >= 2, "Expected at least 2 vendor records"
    eleanor_raw = vendor_records[0]

    # Normalize raw JSON
    bundle = normalize_vendor_patient(eleanor_raw)

    # Validate Bundle Structure
    assert isinstance(bundle, FHIRBundle)
    assert bundle.resourceType == "Bundle"
    assert bundle.id == "bundle-P101"
    assert len(bundle.entry) > 0

    # Extract Resources
    resources = [entry.resource for entry in bundle.entry]
    patient_res = next(r for r in resources if isinstance(r, FHIRPatient))
    observations = [r for r in resources if isinstance(r, FHIRObservation)]
    conditions = [r for r in resources if isinstance(r, FHIRCondition)]
    medications = [r for r in resources if isinstance(r, FHIRMedicationRequest)]
    encounters = [r for r in resources if isinstance(r, FHIREncounter)]

    # Assertions on Patient P101
    assert patient_res.id == "P101"
    assert patient_res.name[0].given == ["Eleanor"]
    assert patient_res.name[0].family == "Vance"
    assert patient_res.gender == "female"

    # Assertions on Observations (Labs)
    assert len(observations) == 2
    hba1c_obs = next(o for o in observations if o.code.coding[0].code == "4548-4")
    assert hba1c_obs.valueQuantity.value == 8.4
    assert hba1c_obs.valueQuantity.unit == "%"

    # Assertions on Conditions
    assert len(conditions) == 2
    diabetes_cond = next(c for c in conditions if c.code.coding[0].code == "E11.9")
    assert diabetes_cond.code.text == "Type 2 Diabetes Mellitus"

    # Assertions on Medications
    assert len(medications) == 2
    metformin_rx = next(m for m in medications if m.medicationCodeableConcept.coding[0].code == "860975")
    assert "Metformin" in metformin_rx.medicationCodeableConcept.text

    # Assertions on Encounters
    assert len(encounters) == 1
    assert encounters[0].id == "ENC-901"

    return bundle


def run_milestone_demo():
    """Runs a visual console demonstration of Module 1 FHIR normalization."""
    print("=" * 80)
    print(" [HOSPITAL] MODULE 1 WORKING MILESTONE DEMO: RAW EHR -> FHIR R4 NORMALIZATION ")
    print("=" * 80)
    
    bundle = test_fhir_normalization_pipeline()
    
    print("\n[OK] Normalization successful! Outputting Normalized FHIR R4 Bundle Summary:")
    print(f"[BUNDLE] ID: {bundle.id} (Total Entries: {len(bundle.entry)})")
    
    for idx, entry in enumerate(bundle.entry, 1):
        res = entry.resource
        print(f"\n--- Entry #{idx}: [{res.resourceType}] (ID: {res.id}) ---")
        if isinstance(res, FHIRPatient):
            print(f"   [PATIENT] Name: {res.name[0].given[0]} {res.name[0].family}")
            print(f"   [ID] MRN: {res.identifier[0].value}")
            print(f"   [INFO] DOB: {res.birthDate} | Gender: {res.gender}")
        elif isinstance(res, FHIRObservation):
            print(f"   [LAB] Test: {res.code.text} (LOINC: {res.code.coding[0].code})")
            print(f"   [VALUE] Result: {res.valueQuantity.value} {res.valueQuantity.unit}")
            print(f"   [TIME] Date: {res.effectiveDateTime}")
        elif isinstance(res, FHIRCondition):
            print(f"   [DIAGNOSIS] Disease: {res.code.text} (ICD-10: {res.code.coding[0].code})")
            print(f"   [TIME] Onset Date: {res.onsetDateTime}")
        elif isinstance(res, FHIRMedicationRequest):
            print(f"   [MEDICATION] Drug: {res.medicationCodeableConcept.text} (RxNorm: {res.medicationCodeableConcept.coding[0].code})")
            print(f"   [STATUS] Status: {res.status} | Intent: {res.intent}")
        elif isinstance(res, FHIREncounter):
            print(f"   [VISIT] Type: {res.class_code.display}")
            print(f"   [TIME] Period: {res.period.start} to {res.period.end}")

    print("\n" + "=" * 80)
    print(" [SUCCESS] MODULE 1 DEMO COMPLETE: All raw vendor records parsed into FHIR schemas!")
    print("=" * 80)



if __name__ == "__main__":
    run_milestone_demo()
