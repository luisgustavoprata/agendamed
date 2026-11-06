"""Repositório dos médicos: cadastro, grade de horários, remoção e lista."""

from datetime import datetime

from agendamed.models import Doctor, to_db_datetime
from agendamed.repositories.base import Page, Repository


class DoctorRepository(Repository):
    """SQL dos médicos. Médicos removidos ficam no banco com `active = 0` (as consultas antigas
    continuam ligadas a eles), mas somem das buscas.
    """

    def create(self, data) -> Doctor:
        """Cadastra um médico. Se o CRM for de um médico removido, ele volta, com os dados novos
        e o histórico antigo.
        """
        removed = self.conn.execute(
            "SELECT id FROM doctors WHERE crm = ? AND active = 0", (data.crm,)
        ).fetchone()
        if removed is not None:
            # O CRM é de um médico removido: ele volta, com os dados novos e o histórico antigo.
            self.conn.execute(
                """UPDATE doctors SET name = ?, specialty = ?, slot_minutes = ?, work_start = ?,
                   work_end = ?, active = 1 WHERE id = ?""",
                (
                    data.name,
                    data.specialty,
                    data.slot_minutes,
                    data.work_start.strftime("%H:%M"),
                    data.work_end.strftime("%H:%M"),
                    removed["id"],
                ),
            )
            return self.get(removed["id"])
        doctor_id = self._insert(
            """INSERT INTO doctors (name, specialty, crm, slot_minutes, work_start, work_end)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                data.name,
                data.specialty,
                data.crm,
                data.slot_minutes,
                data.work_start.strftime("%H:%M"),
                data.work_end.strftime("%H:%M"),
            ),
            "Já existe um médico com este CRM.",
        )
        return self.get(doctor_id)

    def get(self, doctor_id: int) -> Doctor | None:
        """Só médicos ativos: um médico removido não aparece nem recebe consultas."""
        row = self.conn.execute(
            "SELECT * FROM doctors WHERE id = ? AND active = 1", (doctor_id,)
        ).fetchone()
        return Doctor.from_row(row) if row else None

    def count_future_appointments(self, doctor_id: int, now: datetime) -> int:
        """Quantas consultas marcadas o médico tem depois de `now`."""
        return self.conn.execute(
            """SELECT COUNT(*) FROM appointments
               WHERE doctor_id = ? AND status = 'scheduled' AND start_at > ?""",
            (doctor_id, to_db_datetime(now)),
        ).fetchone()[0]

    def deactivate(self, doctor_id: int) -> None:
        """Marca o médico como removido (some das listas e da agenda)."""
        self.conn.execute("UPDATE doctors SET active = 0 WHERE id = ?", (doctor_id,))

    def list(self, *, specialty: str | None, limit: int, offset: int) -> Page:
        """Página de médicos ativos em ordem alfabética. `specialty` filtra pela especialidade
        (parte do nome basta).
        """
        where, params = ["active = 1"], []
        if specialty:
            where.append("specialty LIKE ?")
            params.append(f"%{specialty}%")
        return self._page("SELECT * FROM doctors", where, params, Doctor, "name", limit, offset)
