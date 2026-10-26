"""Regras de agenda puras: não acessam banco nem relógio, por isso são fáceis de testar."""

from datetime import date, datetime, timedelta

from agendamed.errors import BusinessRuleError
from agendamed.models import Doctor

WEEKEND = {5, 6}  # sábado e domingo em datetime.weekday()

Interval = tuple[datetime, datetime]


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Intervalos semiabertos [início, fim): uma consulta que termina às 10h
    não conflita com outra que começa às 10h."""
    return a_start < b_end and b_start < a_end


def working_day_bounds(doctor: Doctor, day: date) -> Interval:
    return datetime.combine(day, doctor.work_start), datetime.combine(day, doctor.work_end)


def validate_booking(doctor: Doctor, start: datetime, now: datetime) -> datetime:
    """Valida o horário pedido e retorna o horário de término da consulta."""
    slot = timedelta(minutes=doctor.slot_minutes)
    end = start + slot

    if start.second or start.microsecond:
        raise BusinessRuleError("Informe o horário sem segundos (ex.: 2030-01-07T10:30).")
    if start <= now:
        raise BusinessRuleError("Não é possível agendar consultas no passado.")
    if start.weekday() in WEEKEND:
        raise BusinessRuleError("O médico não atende aos fins de semana.")

    day_start, day_end = working_day_bounds(doctor, start.date())
    if start < day_start or end > day_end:
        raise BusinessRuleError(
            f"Horário fora do expediente do médico "
            f"({doctor.work_start:%H:%M} às {doctor.work_end:%H:%M})."
        )
    if (start - day_start) % slot:
        raise BusinessRuleError(
            f"O horário deve seguir a grade de {doctor.slot_minutes} em "
            f"{doctor.slot_minutes} minutos a partir de {doctor.work_start:%H:%M}."
        )
    return end


def free_slots(doctor: Doctor, day: date, busy: list[Interval], now: datetime) -> list[datetime]:
    """Lista os horários livres do médico em um dia, ignorando os que já passaram."""
    if day.weekday() in WEEKEND:
        return []

    slot = timedelta(minutes=doctor.slot_minutes)
    current, day_end = working_day_bounds(doctor, day)
    slots = []
    while current + slot <= day_end:
        slot_end = current + slot
        is_busy = any(overlaps(current, slot_end, b_start, b_end) for b_start, b_end in busy)
        if current > now and not is_busy:
            slots.append(current)
        current = slot_end
    return slots
