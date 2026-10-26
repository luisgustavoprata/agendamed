"""Casos de uso de consultas: orquestra regras de agenda, repositórios e transações."""

import sqlite3
from datetime import date, datetime

from agendamed.db import transaction
from agendamed.errors import ConflictError, NotFoundError
from agendamed.models import Appointment, AppointmentStatus, Doctor
from agendamed.repositories import AppointmentRepository, DoctorRepository, PatientRepository
from agendamed.schemas import AppointmentCreate
from agendamed.services.scheduling import free_slots, validate_booking


class AppointmentService:
    def __init__(self, conn: sqlite3.Connection, now: datetime):
        self.conn = conn
        self.now = now
        self.doctors = DoctorRepository(conn)
        self.patients = PatientRepository(conn)
        self.appointments = AppointmentRepository(conn)

    def _get_doctor(self, doctor_id: int) -> Doctor:
        doctor = self.doctors.get(doctor_id)
        if doctor is None:
            raise NotFoundError("Médico não encontrado.")
        return doctor

    def _get_appointment(self, appointment_id: int) -> Appointment:
        appointment = self.appointments.get(appointment_id)
        if appointment is None:
            raise NotFoundError("Consulta não encontrada.")
        return appointment

    def book(self, data: AppointmentCreate) -> Appointment:
        doctor = self._get_doctor(data.doctor_id)
        if self.patients.get(data.patient_id) is None:
            raise NotFoundError("Paciente não encontrado.")

        end_at = validate_booking(doctor, data.start_at, self.now)

        # A checagem de conflito e a inserção acontecem na mesma transação
        # reservada para escrita, evitando agendamentos duplicados concorrentes.
        with transaction(self.conn, immediate=True):
            if self.appointments.find_overlapping(data.start_at, end_at, doctor_id=doctor.id):
                raise ConflictError("O médico já tem uma consulta nesse horário.")
            if self.appointments.find_overlapping(
                data.start_at, end_at, patient_id=data.patient_id
            ):
                raise ConflictError("O paciente já tem uma consulta nesse horário.")
            appointment_id = self.appointments.create(
                doctor_id=doctor.id,
                patient_id=data.patient_id,
                start_at=data.start_at,
                end_at=end_at,
                notes=data.notes,
            )
        return self._get_appointment(appointment_id)

    def cancel(self, appointment_id: int) -> Appointment:
        appointment = self._get_appointment(appointment_id)
        if appointment.status != AppointmentStatus.SCHEDULED:
            raise ConflictError("Apenas consultas agendadas podem ser canceladas.")
        if appointment.start_at <= self.now:
            raise ConflictError("Não é possível cancelar uma consulta que já começou.")
        self.appointments.update_status(appointment_id, AppointmentStatus.CANCELLED)
        return self._get_appointment(appointment_id)

    def complete(self, appointment_id: int) -> Appointment:
        appointment = self._get_appointment(appointment_id)
        if appointment.status != AppointmentStatus.SCHEDULED:
            raise ConflictError("Apenas consultas agendadas podem ser concluídas.")
        if appointment.start_at > self.now:
            raise ConflictError("A consulta ainda não começou.")
        self.appointments.update_status(appointment_id, AppointmentStatus.COMPLETED)
        return self._get_appointment(appointment_id)

    def availability(self, doctor_id: int, day: date) -> list[datetime]:
        doctor = self._get_doctor(doctor_id)
        busy = self.appointments.busy_intervals(doctor.id, day)
        return free_slots(doctor, day, busy, self.now)
