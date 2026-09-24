"""
Mock Healthcare Database Engine.
Provides clinical data access for patient demographics, lab results, medications, and clinical notes.
"""

import json
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


# Global Singleton Database Instance
db = HealthcareDatabase()
