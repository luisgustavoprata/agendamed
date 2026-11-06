"""Prontuário do paciente: ficha clínica (alergias, doenças, remédios) e registros."""

from __future__ import annotations

from agendamed.errors import BusinessRuleError
from agendamed.gestao.base import _row
from agendamed.gestao.schemas import RECORD_KINDS, ClinicalSummaryUpdate, RecordEntryCreate


class ProntuarioMixin:
    """Ficha clínica e registros do prontuário (anamnese, evolução, exames...)."""

    def clinical_summary(self, patient_id: int) -> dict:
        row = self.db.one(
            """SELECT c.allergies, c.conditions, c.medications, c.blood_type, c.notes,
                      c.updated_at, u.full_name AS updated_by
               FROM patient_clinical c LEFT JOIN users u ON u.id = c.updated_by
               WHERE c.patient_id = ? AND c.clinic_id = ?""",
            (patient_id, self.clinic_id),
        )
        empty = dict.fromkeys(
            (
                "allergies",
                "conditions",
                "medications",
                "blood_type",
                "notes",
                "updated_at",
                "updated_by",
            )
        )
        return _row(row) or empty

    def save_clinical_summary(
        self, patient_id: int, data: ClinicalSummaryUpdate, user_id: int, now: str
    ) -> dict:
        values = (
            data.allergies,
            data.conditions,
            data.medications,
            data.blood_type,
            data.notes,
            now,
            user_id,
        )
        exists = self.db.one(
            "SELECT patient_id FROM patient_clinical WHERE patient_id = ? AND clinic_id = ?",
            (patient_id, self.clinic_id),
        )
        if exists:
            self.db.execute(
                """UPDATE patient_clinical SET allergies = ?, conditions = ?, medications = ?,
                   blood_type = ?, notes = ?, updated_at = ?, updated_by = ?
                   WHERE patient_id = ? AND clinic_id = ?""",
                (*values, patient_id, self.clinic_id),
            )
        else:
            self.db.execute(
                """INSERT INTO patient_clinical (allergies, conditions, medications, blood_type,
                   notes, updated_at, updated_by, patient_id, clinic_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*values, patient_id, self.clinic_id),
            )
        return self.clinical_summary(patient_id)

    def record_entries(self, patient_id: int) -> list[dict]:
        rows = self.db.all(
            """SELECT r.id, r.kind, r.content, r.created_at, r.appointment_id, r.doctor_id,
                      d.name AS doctor_name, u.full_name AS author
               FROM record_entries r LEFT JOIN doctors d ON d.id = r.doctor_id
               JOIN users u ON u.id = r.created_by
               WHERE r.patient_id = ? AND r.clinic_id = ?
               ORDER BY r.created_at DESC, r.id DESC""",
            (patient_id, self.clinic_id),
        )
        return [{**dict(r), "kind_label": RECORD_KINDS[r["kind"]]} for r in rows]

    def add_record_entry(
        self,
        patient_id: int,
        data: RecordEntryCreate,
        doctor_id: int | None,
        user_id: int,
        now: str,
    ) -> dict:
        if data.appointment_id is not None:
            appointment = self.require_appointment(data.appointment_id)
            if appointment["patient_id"] != patient_id:
                raise BusinessRuleError("A consulta informada é de outro paciente.")
        entry_id = self.db.insert(
            """INSERT INTO record_entries (clinic_id, patient_id, doctor_id, appointment_id, kind,
                                           content, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self.clinic_id,
                patient_id,
                doctor_id,
                data.appointment_id,
                data.kind,
                data.content,
                user_id,
                now,
            ),
        )
        return next(e for e in self.record_entries(patient_id) if e["id"] == entry_id)
