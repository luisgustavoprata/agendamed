"""Repositório dos pacientes: cadastro, busca por nome ou CPF e edição."""

import sqlite3

from agendamed.errors import ConflictError
from agendamed.models import Patient
from agendamed.repositories.base import Page, Repository


class PatientRepository(Repository):
    def create(self, data) -> Patient:
        patient_id = self._insert(
            """INSERT INTO patients (name, cpf, email, phone, birth_date)
               VALUES (?, ?, ?, ?, ?)""",
            (data.name, data.cpf, data.email, data.phone, data.birth_date.isoformat()),
            "Já existe um paciente com este CPF.",
        )
        return self.get(patient_id)

    def get(self, patient_id: int) -> Patient | None:
        row = self.conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        return Patient.from_row(row) if row else None

    _EDITABLE = ("name", "cpf", "email", "phone", "birth_date")

    def update(self, patient_id: int, changes: dict) -> Patient:
        columns = [name for name in self._EDITABLE if name in changes]
        values = [
            changes[name].isoformat() if name == "birth_date" else changes[name] for name in columns
        ]
        assignments = ", ".join(f"{name} = ?" for name in columns)
        try:
            self.conn.execute(
                f"UPDATE patients SET {assignments} WHERE id = ?", (*values, patient_id)
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError("Já existe um paciente com este CPF.") from exc
        return self.get(patient_id)

    def list(self, *, search: str | None, limit: int, offset: int) -> Page:
        where, params = [], []
        if search:
            where.append("(name LIKE ? OR cpf LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        return self._page("SELECT * FROM patients", where, params, Patient, "name", limit, offset)
