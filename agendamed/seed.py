"""Dados de demonstração para explorar a API rapidamente."""

import sqlite3
from datetime import date, datetime, time, timedelta

from flask import current_app

from agendamed.errors import BusinessRuleError, ConflictError
from agendamed.repositories import DoctorRepository, PatientRepository, UserRepository
from agendamed.schemas import AppointmentCreate, DoctorCreate, PatientCreate
from agendamed.security import hash_password
from agendamed.services.appointments import AppointmentService

DOCTORS = [
    {"name": "Dra. Helena Prado", "specialty": "Cardiologia", "crm": "123456/SP"},
    {"name": "Dr. Rafael Moura", "specialty": "Pediatria", "crm": "654321/GO", "slot_minutes": 20},
    {
        "name": "Dra. Camila Rocha",
        "specialty": "Dermatologia",
        "crm": "112233/MG",
        "work_start": "09:00",
        "work_end": "15:00",
        "slot_minutes": 45,
    },
]

PATIENTS = [
    {"name": "Ana Souza", "cpf": "529.982.247-25", "email": "ana@exemplo.com",
     "birth_date": "1994-03-12", "phone": "(64) 99999-1111"},
    {"name": "Bruno Lima", "cpf": "526.018.159-06", "email": "bruno@exemplo.com",
     "birth_date": "1988-11-02"},
    {"name": "Carla Mendes", "cpf": "083.016.613-05", "email": "carla@exemplo.com",
     "birth_date": "2015-07-21"},
    {"name": "Daniel Ferreira", "cpf": "186.091.390-34", "email": "daniel@exemplo.com",
     "birth_date": "1971-05-30", "phone": "(62) 98888-2222"},
    {"name": "Elisa Martins", "cpf": "996.030.824-30", "email": "elisa@exemplo.com",
     "birth_date": "1959-09-14"},
    {"name": "Felipe Andrade", "cpf": "347.215.908-14", "email": "felipe@exemplo.com",
     "birth_date": "2001-01-08", "phone": "(64) 97777-3333"},
]

# (índice do médico, índice do paciente, horário, observação). Os horários respeitam
# a grade de cada médico: 30 min a partir das 08:00, 20 min a partir das 08:00 e
# 45 min a partir das 09:00.
APPOINTMENTS = [
    (0, 0, time(9, 0), "Consulta de rotina"),
    (0, 1, time(10, 0), "Retorno com resultado de exames"),
    (0, 3, time(11, 30), "Primeira consulta"),
    (0, 4, time(14, 0), "Avaliação pré-operatória"),
    (0, 5, time(15, 30), None),
    (1, 2, time(10, 0), "Acompanhamento de crescimento"),
    (2, 0, time(10, 30), "Avaliação de pele"),
]


def _working_days(start: date, count: int) -> list[date]:
    """Os próximos `count` dias úteis, começando por `start` se ele for dia útil."""
    days, day = [], start
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def seed(conn: sqlite3.Connection) -> None:
    """Cria dados de demonstração. Não faz nada se eles já existirem."""
    users = UserRepository(conn)
    if users.get_by_email("admin@agendamed.dev") is None:
        iterations = current_app.config["PASSWORD_HASH_ITERATIONS"]
        password_hash = hash_password("admin12345", iterations)
        try:
            users.create("admin@agendamed.dev", "Administrador", password_hash)
        except ConflictError:
            return  # outro processo está populando o banco ao mesmo tempo

    doctors, patients = DoctorRepository(conn), PatientRepository(conn)
    doctor_ids, patient_ids = [], []
    for raw in DOCTORS:
        try:
            doctor_ids.append(doctors.create(DoctorCreate.model_validate(raw)).id)
        except ConflictError:
            return  # dados já populados
    for raw in PATIENTS:
        patient_ids.append(patients.create(PatientCreate.model_validate(raw)).id)

    # As datas são relativas a "hoje": a demonstração sempre mostra uma agenda atual,
    # mesmo quando o servidor reinicia com o banco vazio.
    now = current_app.config["CLOCK"]()
    service = AppointmentService(conn, now)
    for day in _working_days(now.date(), 2):
        for doctor_index, patient_index, start, notes in APPOINTMENTS:
            try:
                service.book(
                    AppointmentCreate(
                        doctor_id=doctor_ids[doctor_index],
                        patient_id=patient_ids[patient_index],
                        start_at=datetime.combine(day, start),
                        notes=notes,
                    )
                )
            except BusinessRuleError:
                continue  # horário de hoje que já passou
