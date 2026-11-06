"""Prescrições: receitas, atestados, pedidos de exame e relatórios médicos."""

from __future__ import annotations

import json

from agendamed.errors import NotFoundError
from agendamed.gestao.schemas import PRESCRIPTION_KINDS, PrescriptionCreate


class PrescricoesMixin:
    """Criar e listar os documentos do paciente."""

    _PRESCRIPTION_SELECT = """
        SELECT pr.id, pr.kind, pr.items, pr.text, pr.created_at, pr.patient_id, pr.doctor_id,
               d.name AS doctor_name, d.crm AS doctor_crm, d.specialty AS doctor_specialty,
               p.name AS patient_name, p.cpf AS patient_cpf, p.birth_date AS patient_birth_date
        FROM prescriptions pr JOIN doctors d ON d.id = pr.doctor_id
        JOIN patients p ON p.id = pr.patient_id
    """

    def _prescription(self, row) -> dict:
        """Converte a linha do banco: os itens saem do JSON e entra o nome do tipo."""
        item = dict(row)
        item["items"] = json.loads(item["items"] or "[]")
        item["kind_label"] = PRESCRIPTION_KINDS[item["kind"]]
        return item

    def prescriptions(self, patient_id: int) -> list[dict]:
        """Os documentos do paciente (receitas, atestados...), do mais novo para o mais antigo."""
        rows = self.db.all(
            f"{self._PRESCRIPTION_SELECT} WHERE pr.patient_id = ? AND pr.clinic_id = ? "
            "ORDER BY pr.created_at DESC, pr.id DESC",
            (patient_id, self.clinic_id),
        )
        return [self._prescription(r) for r in rows]

    def prescription(self, prescription_id: int) -> dict:
        """Um documento pelo id; erro 404 se não for desta clínica."""
        row = self.db.one(
            f"{self._PRESCRIPTION_SELECT} WHERE pr.id = ? AND pr.clinic_id = ?",
            (prescription_id, self.clinic_id),
        )
        if row is None:
            raise NotFoundError("Prescrição não encontrada.")
        return self._prescription(row)

    def add_prescription(
        self, patient_id: int, data: PrescriptionCreate, doctor_id: int, user_id: int, now: str
    ) -> dict:
        """Cria um documento para o paciente, em nome do médico."""
        items = json.dumps([i.model_dump() for i in data.items], ensure_ascii=False)
        new_id = self.db.insert(
            """INSERT INTO prescriptions (clinic_id, patient_id, doctor_id, kind, items, text,
                                          created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (self.clinic_id, patient_id, doctor_id, data.kind, items, data.text, user_id, now),
        )
        return self.prescription(new_id)
