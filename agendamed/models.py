"""Entidades de domínio (imutáveis) e sua conversão de/para o banco e JSON."""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum

from agendamed.validators import format_cpf


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


def to_db_datetime(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def to_api_datetime(value: datetime) -> str:
    return value.isoformat(timespec="minutes")


@dataclass(frozen=True, slots=True)
class User:
    id: int
    email: str
    full_name: str
    password_hash: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "User":
        return cls(
            id=row["id"],
            email=row["email"],
            full_name=row["full_name"],
            password_hash=row["password_hash"],
        )

    def to_dict(self) -> dict:
        return {"id": self.id, "email": self.email, "full_name": self.full_name}


@dataclass(frozen=True, slots=True)
class Doctor:
    id: int
    name: str
    specialty: str
    crm: str
    slot_minutes: int
    work_start: time
    work_end: time

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Doctor":
        return cls(
            id=row["id"],
            name=row["name"],
            specialty=row["specialty"],
            crm=row["crm"],
            slot_minutes=row["slot_minutes"],
            work_start=time.fromisoformat(row["work_start"]),
            work_end=time.fromisoformat(row["work_end"]),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "specialty": self.specialty,
            "crm": self.crm,
            "slot_minutes": self.slot_minutes,
            "work_start": self.work_start.strftime("%H:%M"),
            "work_end": self.work_end.strftime("%H:%M"),
        }


@dataclass(frozen=True, slots=True)
class Patient:
    id: int
    name: str
    cpf: str
    email: str
    phone: str | None
    birth_date: date

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Patient":
        return cls(
            id=row["id"],
            name=row["name"],
            cpf=row["cpf"],
            email=row["email"],
            phone=row["phone"],
            birth_date=date.fromisoformat(row["birth_date"]),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "cpf": format_cpf(self.cpf),
            "email": self.email,
            "phone": self.phone,
            "birth_date": self.birth_date.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class Appointment:
    id: int
    doctor_id: int
    patient_id: int
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus
    notes: str | None
    doctor_name: str | None = None
    patient_name: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Appointment":
        keys = row.keys()
        return cls(
            id=row["id"],
            doctor_id=row["doctor_id"],
            patient_id=row["patient_id"],
            start_at=datetime.fromisoformat(row["start_at"]),
            end_at=datetime.fromisoformat(row["end_at"]),
            status=AppointmentStatus(row["status"]),
            notes=row["notes"],
            doctor_name=row["doctor_name"] if "doctor_name" in keys else None,
            patient_name=row["patient_name"] if "patient_name" in keys else None,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "doctor": {"id": self.doctor_id, "name": self.doctor_name},
            "patient": {"id": self.patient_id, "name": self.patient_name},
            "start_at": to_api_datetime(self.start_at),
            "end_at": to_api_datetime(self.end_at),
            "status": self.status.value,
            "notes": self.notes,
        }
