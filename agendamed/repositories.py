"""Camada de acesso a dados: todo o SQL da aplicação fica aqui."""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from agendamed.errors import ConflictError
from agendamed.models import (
    Appointment,
    AppointmentStatus,
    Doctor,
    Patient,
    User,
    to_db_datetime,
)


@dataclass(frozen=True, slots=True)
class Page:
    items: list
    total: int
    limit: int
    offset: int

    def to_dict(self) -> dict:
        return {
            "items": [item.to_dict() for item in self.items],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
        }


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _insert(self, sql: str, params: tuple, conflict_message: str) -> int:
        try:
            cursor = self.conn.execute(sql, params)
        except sqlite3.IntegrityError as exc:
            raise ConflictError(conflict_message) from exc
        return cursor.lastrowid

    def _page(self, base_sql, where, params, model, order_by, limit, offset) -> Page:
        where_sql = f" WHERE {' AND '.join(where)}" if where else ""
        total = self.conn.execute(
            f"SELECT COUNT(*) FROM ({base_sql}{where_sql})", params
        ).fetchone()[0]
        rows = self.conn.execute(
            f"{base_sql}{where_sql} ORDER BY {order_by} LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return Page([model.from_row(row) for row in rows], total, limit, offset)


class UserRepository(Repository):
    def create(self, email: str, full_name: str, password_hash: str) -> User:
        user_id = self._insert(
            "INSERT INTO users (email, full_name, password_hash) VALUES (?, ?, ?)",
            (email, full_name, password_hash),
            "Já existe um usuário com este e-mail.",
        )
        return self.get(user_id)

    def get(self, user_id: int) -> User | None:
        row = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return User.from_row(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        row = self.conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return User.from_row(row) if row else None


class DoctorRepository(Repository):
    def create(self, data) -> Doctor:
        removed = self.conn.execute(
            "SELECT id FROM doctors WHERE crm = ? AND active = 0", (data.crm,)
        ).fetchone()
        if removed is not None:
            # O CRM é de um médico removido: ele volta, com os dados novos e o histórico antigo.
            self.conn.execute(
                """UPDATE doctors SET name = ?, specialty = ?, slot_minutes = ?, work_start = ?,
                   work_end = ?, active = 1 WHERE id = ?""",
                (
                    data.name, data.specialty, data.slot_minutes,
                    data.work_start.strftime("%H:%M"), data.work_end.strftime("%H:%M"),
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
        return self.conn.execute(
            """SELECT COUNT(*) FROM appointments
               WHERE doctor_id = ? AND status = 'scheduled' AND start_at > ?""",
            (doctor_id, to_db_datetime(now)),
        ).fetchone()[0]

    def deactivate(self, doctor_id: int) -> None:
        self.conn.execute("UPDATE doctors SET active = 0 WHERE id = ?", (doctor_id,))

    def list(self, *, specialty: str | None, limit: int, offset: int) -> Page:
        where, params = ["active = 1"], []
        if specialty:
            where.append("specialty LIKE ?")
            params.append(f"%{specialty}%")
        return self._page(
            "SELECT * FROM doctors", where, params, Doctor, "name", limit, offset
        )


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

    def list(self, *, search: str | None, limit: int, offset: int) -> Page:
        where, params = [], []
        if search:
            where.append("(name LIKE ? OR cpf LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        return self._page(
            "SELECT * FROM patients", where, params, Patient, "name", limit, offset
        )


class AppointmentRepository(Repository):
    _SELECT = """
        SELECT a.*, d.name AS doctor_name, p.name AS patient_name
        FROM appointments a
        JOIN doctors d ON d.id = a.doctor_id
        JOIN patients p ON p.id = a.patient_id
    """

    def create(
        self, *, doctor_id: int, patient_id: int, start_at: datetime, end_at: datetime,
        notes: str | None,
    ) -> int:
        return self._insert(
            """INSERT INTO appointments (doctor_id, patient_id, start_at, end_at, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (doctor_id, patient_id, to_db_datetime(start_at), to_db_datetime(end_at), notes),
            "Não foi possível registrar a consulta.",
        )

    def get(self, appointment_id: int) -> Appointment | None:
        row = self.conn.execute(f"{self._SELECT} WHERE a.id = ?", (appointment_id,)).fetchone()
        return Appointment.from_row(row) if row else None

    def find_overlapping(
        self, start_at: datetime, end_at: datetime, *, doctor_id: int | None = None,
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
        self, *, doctor_id: int | None, patient_id: int | None, day: date | None,
        status: AppointmentStatus | None, limit: int, offset: int,
    ) -> Page:
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
        return self._page(
            self._SELECT, where, params, Appointment, "start_at", limit, offset
        )

    def update_status(self, appointment_id: int, status: AppointmentStatus) -> None:
        self.conn.execute(
            "UPDATE appointments SET status = ? WHERE id = ?", (status.value, appointment_id)
        )
