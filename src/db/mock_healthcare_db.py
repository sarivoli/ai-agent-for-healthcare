"""
Mock Healthcare Database Engine.
Provides clinical data access for patient demographics, lab results, medications, and clinical notes.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.fhir.normalizer import normalize_vendor_patient


class HealthcareDatabase:
    def __init__(self, data_file: Optional[Path] = None):
        if data_file is None:
            data_file = Path(__file__).parent.parent / "fhir" / "mock_vendor_data.json"
        
        self.data_file = data_file
        self._raw_data: List[Dict[str, Any]] = []
        self._clinical_notes: Dict[str, List[Dict[str, Any]]] = {}
        self._load_database()

    def reset(self):
        """Reset in-memory database to initial state."""
        self._load_database()

    def _load_database(self):
        if self.data_file.exists():
            with open(self.data_file, "r", encoding="utf-8") as f:
                self._raw_data = json.load(f)
        
        # Additional mock clinical notes database
        self._clinical_notes = {
            "P101": [
                {
                    "note_id": "NOTE-101",
                    "author": "Dr. Sarah Jenkins, MD",
                    "date": "2026-08-15",
                    "category": "Progress Note",
                    "content": "Patient presents for routine diabetes follow-up. HbA1c remains elevated at 8.4%. Patient reports occasional non-adherence to evening Metformin due to GI upset. Blood pressure 142/90 mmHg. Instructed patient on low glycemic diet, adjusted Metformin dosing schedule, and renewed Lisinopril 10mg daily."
                }
            ],
            "P102": [
                {
                    "note_id": "NOTE-102",
                    "author": "Dr. Robert Vance, MD",
                    "date": "2026-09-01",
                    "category": "Annual Exam Note",
                    "content": "Annual physical exam completed. Total cholesterol 245 mg/dL. Patient reports mild muscle fatigue. Discussed lipid management and diet modifications. Advised continuing Atorvastatin 20mg daily with follow-up lipid panel in 6 months."
                }
            ]
        }

    def get_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        patient_id_clean = patient_id.upper().strip()
        for record in self._raw_data:
            if record.get("pat_id", "").upper() == patient_id_clean:
                bundle = normalize_vendor_patient(record)
                return bundle.model_dump()
        return None

    def get_lab_results(self, patient_id: str, test_name: Optional[str] = None) -> List[Dict[str, Any]]:
        patient_id_clean = patient_id.upper().strip()
        labs = []
        for record in self._raw_data:
            if record.get("pat_id", "").upper() == patient_id_clean:
                raw_labs = record.get("lab_records", [])
                for lab in raw_labs:
                    if test_name:
                        if test_name.lower() in lab.get("name", "").lower():
                            labs.append(lab)
                    else:
                        labs.append(lab)
        # Sort newest-first so latest observations always take priority
        labs.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)
        return labs

    def get_medications(self, patient_id: str) -> List[Dict[str, Any]]:
        patient_id_clean = patient_id.upper().strip()
        for record in self._raw_data:
            if record.get("pat_id", "").upper() == patient_id_clean:
                return record.get("prescriptions", [])
        return []

    def get_clinical_notes(self, patient_id: str) -> List[Dict[str, Any]]:
        patient_id_clean = patient_id.upper().strip()
        return self._clinical_notes.get(patient_id_clean, [])

    def create_medication_order(self, patient_id: str, drug_name: str, dosage: str, frequency: str) -> Dict[str, Any]:
        patient_id_clean = patient_id.upper().strip()
        order_id = f"RX-NEW-{len(self.get_medications(patient_id_clean)) + 501}"
        new_med = {
            "rx_id": order_id,
            "drug_name": f"{drug_name} {dosage}",
            "status": "active",
            "frequency": frequency,
            "ordered_date": "2026-09-23"
        }
        for record in self._raw_data:
            if record.get("pat_id", "").upper() == patient_id_clean:
                if "prescriptions" not in record:
                    record["prescriptions"] = []
                record["prescriptions"].append(new_med)
                break
        return {"status": "success", "order_id": order_id, "medication": new_med}

    def update_patient_note(self, patient_id: str, note_content: str, author: str) -> Dict[str, Any]:
        patient_id_clean = patient_id.upper().strip()
        note_id = f"NOTE-NEW-{len(self.get_clinical_notes(patient_id_clean)) + 201}"
        new_note = {
            "note_id": note_id,
            "author": author,
            "date": "2026-09-23",
            "category": "Progress Note Update",
            "content": note_content
        }
        if patient_id_clean not in self._clinical_notes:
            self._clinical_notes[patient_id_clean] = []
        self._clinical_notes[patient_id_clean].append(new_note)
        return {"status": "success", "note_id": note_id, "note": new_note}

    def add_care_gap_remediation(self, patient_id: str, gap_id: str, action_taken: str) -> Dict[str, Any]:
        patient_id_clean = patient_id.upper().strip()
        remediation_id = f"REM-{gap_id}-001"
        record = {
            "remediation_id": remediation_id,
            "patient_id": patient_id_clean,
            "gap_id": gap_id,
            "action_taken": action_taken,
            "timestamp": "2026-09-23T18:45:00Z"
        }
        return {"status": "success", "remediation_id": remediation_id, "remediation": record}

    def add_lab_result(self, patient_id: str, test_name: str, value: Any, unit: str = "", loinc: str = "") -> Dict[str, Any]:
        """Dynamically appends a new clinical lab observation for patient_id."""
        patient_id_clean = patient_id.upper().strip()
        lab_id = f"LAB-NEW-{len(self.get_lab_results(patient_id_clean)) + 101}"
        
        # Auto-resolve standard LOINC & units if not provided
        t_lower = test_name.lower()
        if "a1c" in t_lower or "hba1c" in t_lower:
            loinc = loinc or "4548-4"
            unit = unit or "%"
            test_name = "Hemoglobin A1c (HbA1c)"
        elif "bp" in t_lower or "blood pressure" in t_lower or "systolic" in t_lower:
            loinc = loinc or "8480-6"
            unit = unit or "mmHg"
        elif "glucose" in t_lower or "sugar" in t_lower:
            loinc = loinc or "2345-7"
            unit = unit or "mg/dL"
            if "fast" in t_lower:
                test_name = "Fasting Blood Glucose"
            elif t_lower in ["sugar", "blood sugar"]:
                test_name = "Blood Glucose"
        elif "cbc" in t_lower or "complete blood count" in t_lower:
            loinc = loinc or "58410-2"
            unit = unit or "K/uL"
            test_name = "Complete Blood Count (CBC)"
        elif "platelet" in t_lower:
            loinc = loinc or "777-3"
            unit = unit or "K/uL"
            test_name = "Platelet Count"
        elif "wbc" in t_lower or "white blood" in t_lower:
            loinc = loinc or "6690-2"
            unit = unit or "K/uL"
            test_name = "White Blood Cell Count"
        elif "cholesterol" in t_lower:
            loinc = loinc or "2093-3"
            unit = unit or "mg/dL"
        elif "potassium" in t_lower:
            loinc = loinc or "2823-3"
            unit = unit or "mEq/L"
        elif not loinc:
            loinc = "9999-9"

        try:
            numeric_val = float(value)
        except (ValueError, TypeError):
            numeric_val = value

        current_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_lab = {
            "test_id": lab_id,
            "name": test_name,
            "loinc": loinc,
            "result_val": numeric_val,
            "unit_meas": unit,
            "timestamp": current_iso
        }
        for record in self._raw_data:
            if record.get("pat_id", "").upper() == patient_id_clean:
                if "lab_records" not in record:
                    record["lab_records"] = []
                record["lab_records"].insert(0, new_lab)
                break
        return {"status": "success", "lab_id": lab_id, "lab_result": new_lab}


# Global Singleton Database Instance
db = HealthcareDatabase()
