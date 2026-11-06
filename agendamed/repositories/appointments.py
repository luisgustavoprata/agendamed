"""Repositório das consultas: marcar, mudar o status, conflitos e horários ocupados."""

from datetime import date, datetime, timedelta

from agendamed.models import Appointment, AppointmentStatus, to_db_datetime
from agendamed.repositories.base import Page, Repository


class AppointmentRepository(Repository):
    """SQL das consultas. `_SELECT` junta os nomes do médico e do paciente, usados nas telas."""

    _SELECT = """
        SELECT a.*, d.name AS doctor_name, p.name AS patient_name
        FROM appointments a
        JOIN doctors d ON d.id = a.doctor_id
        JOIN patients p ON p.id = a.patient_id
    """

    def create(
        self,
        *,
        doctor_id: int,
        patient_id: int,
        start_at: datetime,
        end_at: datetime,
        notes: str | None,
    ) -> int:
        """Grava uma consulta nova e devolve o id. Não confere conflitos: isso é feito antes, no
        serviço (AppointmentService.book).
        """
        return self._insert(
            """INSERT INTO appointments (doctor_id, patient_id, start_at, end_at, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (doctor_id, patient_id, to_db_datetime(start_at), to_db_datetime(end_at), notes),
            "Não foi possível registrar a consulta.",
        )

    def get(self, appointment_id: int) -> Appointment | None:
        """A consulta pelo id, com os nomes; ou None."""
        row = self.conn.execute(f"{self._SELECT} WHERE a.id = ?", (appointment_id,)).fetchone()
        return Appointment.from_row(row) if row else None

    def find_overlapping(
        self,
        start_at: datetime,
        end_at: datetime,
        *,
        doctor_id: int | None = None,
        patient_id: int | None = None,
    ) -> Appointment | None:
        """Busca uma consulta ativa que se sobreponha ao intervalo [start_at, end_at)."""
        sql = "SELECT * FROM appointments WHERE status = ? AND start_at < ? AND end_at > ?"
        params: list = [
            AppointmentStatus.SCHEDULED.value,
            to_db_datetime(end_at),
            to_db_datetime(start_at),
        ]
        if doctor_id is not None:
            sql += " AND doctor_id = ?"
            params.append(doctor_id)
        if patient_id is not None:
            sql += " AND patient_id = ?"
            params.append(patient_id)
        row = self.conn.execute(f"{sql} LIMIT 1", params).fetchone()
        return Appointment.from_row(row) if row else None

    def busy_intervals(self, doctor_id: int, day: date) -> list[tuple[datetime, datetime]]:
        """Os horários ocupados do médico num dia: lista de (início, fim)."""
        start = datetime.combine(day, datetime.min.time())
        rows = self.conn.execute(
            """SELECT start_at, end_at FROM appointments
               WHERE doctor_id = ? AND status = ? AND start_at < ? AND end_at > ?""",
            (
                doctor_id,
                AppointmentStatus.SCHEDULED.value,
                to_db_datetime(start + timedelta(days=1)),
                to_db_datetime(start),
            ),
        ).fetchall()
        return [
            (datetime.fromisoformat(row["start_at"]), datetime.fromisoformat(row["end_at"]))
            for row in rows
        ]

    def list(
        self,
        *,
        doctor_id: int | None,
        patient_id: int | None,
        day: date | None,
        status: AppointmentStatus | None,
        limit: int,
        offset: int,
    ) -> Page:
        """Página de consultas por ordem de horário, com filtros opcionais por médico, paciente,
        dia e situação.
        """
        where, params = [], []
        if doctor_id is not None:
            where.append("a.doctor_id = ?")
            params.append(doctor_id)
        if patient_id is not None:
            where.append("a.patient_id = ?")
            params.append(patient_id)
        if day is not None:
            start = datetime.combine(day, datetime.min.time())
            where.append("a.start_at >= ? AND a.start_at < ?")
            params.extend([to_db_datetime(start), to_db_datetime(start + timedelta(days=1))])
        if status is not None:
            where.append("a.status = ?")
            params.append(status.value)
        return self._page(self._SELECT, where, params, Appointment, "start_at", limit, offset)

    def update_status(self, appointment_id: int, status: AppointmentStatus) -> None:
        """Muda a situação da consulta (agendada, cancelada ou concluída)."""
        self.conn.execute(
            "UPDATE appointments SET status = ? WHERE id = ?", (status.value, appointment_id)
        )
