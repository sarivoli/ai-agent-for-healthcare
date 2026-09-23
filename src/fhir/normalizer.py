"""
FHIR Normalization Engine.
Translates legacy vendor EHR payloads into standardized HL7 FHIR R4 resource bundles.
"""

from typing import Dict, Any, List
from src.fhir.schemas import (
    FHIRPatient,
    FHIRObservation,
    FHIRCondition,
    FHIRMedicationRequest,
    FHIREncounter,
    FHIRBundle,
    BundleEntry,
    HumanName,
    Identifier,
    CodeableConcept,
    Coding,
    Quantity,
    Reference,
    Period
)


def normalize_vendor_patient(vendor_record: Dict[str, Any]) -> FHIRBundle:
    """
    Transforms a raw legacy vendor patient dictionary into a standardized FHIR R4 Bundle.
    """
    pat_id = vendor_record.get("pat_id", "P000")
    
    # 1. Create Patient Resource
    patient = FHIRPatient(
        id=pat_id,
        identifier=[
            Identifier(
                system="urn:oid:2.16.840.1.113883.4.1",  # MRN System OID
                value=vendor_record.get("mrn_number", f"MRN-{pat_id}")
            )
        ],
        name=[
            HumanName(
                use="official",
                family=vendor_record.get("lname", "Unknown"),
                given=[vendor_record.get("fname", "Unknown")]
            )
        ],
        gender=vendor_record.get("sex", "unknown").lower(),
        birthDate=vendor_record.get("dob_str")
    )
    
    entries = [BundleEntry(fullUrl=f"Patient/{pat_id}", resource=patient)]
    patient_ref = Reference(reference=f"Patient/{pat_id}", display=f"{patient.name[0].given[0]} {patient.name[0].family}")

    # 2. Normalize Lab Records -> Observations
    for lab in vendor_record.get("lab_records", []):
        obs = FHIRObservation(
            id=lab.get("test_id", f"OBS-{pat_id}"),
            status="final",
            code=CodeableConcept(
                coding=[
                    Coding(
                        system="http://loinc.org",
                        code=lab.get("loinc", "UNKNOWN"),
                        display=lab.get("name")
                    )
                ],
                text=lab.get("name")
            ),
            subject=patient_ref,
            valueQuantity=Quantity(
                value=float(lab.get("result_val", 0.0)),
                unit=lab.get("unit_meas", ""),
                code=lab.get("unit_meas")
            ),
            effectiveDateTime=lab.get("timestamp")
        )
        entries.append(BundleEntry(fullUrl=f"Observation/{obs.id}", resource=obs))

    # 3. Normalize Diagnoses -> Conditions
    for diag in vendor_record.get("diagnoses_list", []):
        cond = FHIRCondition(
            id=diag.get("diag_id", f"COND-{pat_id}"),
            code=CodeableConcept(
                coding=[
                    Coding(
                        system="http://hl7.org/fhir/sid/icd-10-cm",
                        code=diag.get("icd10", "UNKNOWN"),
                        display=diag.get("disease_name")
                    )
                ],
                text=diag.get("disease_name")
            ),
            subject=patient_ref,
            onsetDateTime=diag.get("diagnosed_date")
        )
        entries.append(BundleEntry(fullUrl=f"Condition/{cond.id}", resource=cond))

    # 4. Normalize Prescriptions -> MedicationRequests
    for rx in vendor_record.get("prescriptions", []):
        med_req = FHIRMedicationRequest(
            id=rx.get("rx_id", f"RX-{pat_id}"),
            status="active",
            intent="order",
            medicationCodeableConcept=CodeableConcept(
                coding=[
                    Coding(
                        system="http://www.nlm.nih.gov/research/umls/rxnorm",
                        code=rx.get("rxnorm", "UNKNOWN"),
                        display=rx.get("drug_name")
                    )
                ],
                text=rx.get("drug_name")
            ),
            subject=patient_ref,
            authoredOn=rx.get("date_prescribed")
        )
        entries.append(BundleEntry(fullUrl=f"MedicationRequest/{med_req.id}", resource=med_req))

    # 5. Normalize Visits -> Encounters
    for visit in vendor_record.get("visits", []):
        enc = FHIREncounter(
            id=visit.get("visit_id", f"ENC-{pat_id}"),
            status="finished",
            class_code=Coding(
                system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
                code="AMB",
                display=visit.get("visit_type", "Ambulatory")
            ),
            subject=patient_ref,
            period=Period(
                start=visit.get("start_time", ""),
                end=visit.get("end_time")
            )
        )
        entries.append(BundleEntry(fullUrl=f"Encounter/{enc.id}", resource=enc))

    return FHIRBundle(
        id=f"bundle-{pat_id}",
        type="collection",
        entry=entries
    )
