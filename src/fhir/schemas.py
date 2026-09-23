"""
FHIR R4 Resource Schemas using Pydantic v2.
Defines standardized clinical data structures aligned with HL7 FHIR R4 specifications.
"""

from typing import List, Optional, Union
from pydantic import BaseModel, Field


class Coding(BaseModel):
    system: Optional[str] = None
    code: Optional[str] = None
    display: Optional[str] = None


class CodeableConcept(BaseModel):
    coding: List[Coding] = Field(default_factory=list)
    text: Optional[str] = None


class Identifier(BaseModel):
    system: Optional[str] = None
    value: str


class HumanName(BaseModel):
    use: str = "official"
    family: str
    given: List[str] = Field(default_factory=list)


class Quantity(BaseModel):
    value: float
    unit: str
    system: Optional[str] = "http://unitsofmeasure.org"
    code: Optional[str] = None


class Reference(BaseModel):
    reference: str  # e.g., "Patient/P101"
    display: Optional[str] = None


class Period(BaseModel):
    start: str
    end: Optional[str] = None


class FHIRResource(BaseModel):
    resourceType: str
    id: str


class FHIRPatient(FHIRResource):
    resourceType: str = "Patient"
    identifier: List[Identifier] = Field(default_factory=list)
    name: List[HumanName] = Field(default_factory=list)
    gender: Optional[str] = None  # male | female | other | unknown
    birthDate: Optional[str] = None  # YYYY-MM-DD


class FHIRObservation(FHIRResource):
    resourceType: str = "Observation"
    status: str = "final"  # registered | preliminary | final | amended
    code: CodeableConcept
    subject: Reference
    valueQuantity: Optional[Quantity] = None
    valueString: Optional[str] = None
    effectiveDateTime: Optional[str] = None


class FHIRCondition(FHIRResource):
    resourceType: str = "Condition"
    clinicalStatus: CodeableConcept = Field(
        default_factory=lambda: CodeableConcept(
            coding=[Coding(system="http://terminology.hl7.org/CodeSystem/condition-clinical", code="active", display="Active")]
        )
    )
    code: CodeableConcept
    subject: Reference
    onsetDateTime: Optional[str] = None


class FHIRMedicationRequest(FHIRResource):
    resourceType: str = "MedicationRequest"
    status: str = "active"  # active | completed | cancelled | stopped
    intent: str = "order"
    medicationCodeableConcept: CodeableConcept
    subject: Reference
    authoredOn: Optional[str] = None


class FHIREncounter(FHIRResource):
    resourceType: str = "Encounter"
    status: str = "finished"  # planned | in-progress | finished
    class_code: Optional[Coding] = None  # AMB (ambulatory), IMP (inpatient)
    subject: Reference
    period: Optional[Period] = None


class BundleEntry(BaseModel):
    fullUrl: Optional[str] = None
    resource: Union[FHIRPatient, FHIRObservation, FHIRCondition, FHIRMedicationRequest, FHIREncounter]


class FHIRBundle(FHIRResource):
    resourceType: str = "Bundle"
    type: str = "collection"
    entry: List[BundleEntry] = Field(default_factory=list)
