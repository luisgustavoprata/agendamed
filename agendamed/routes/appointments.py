from flask import Blueprint, request, url_for

from agendamed.db import get_db
from agendamed.errors import BadRequestError, NotFoundError
from agendamed.models import AppointmentStatus
from agendamed.repositories import AppointmentRepository
from agendamed.routes._helpers import (
    now,
    pagination,
    parse_body,
    query_date,
    query_int,
    require_auth,
)
from agendamed.schemas import AppointmentCreate
from agendamed.services.appointments import AppointmentService

bp = Blueprint("appointments", __name__, url_prefix="/appointments")
bp.before_request(require_auth)


def _service() -> AppointmentService:
    return AppointmentService(get_db(), now())


@bp.post("")
def create_appointment():
    appointment = _service().book(parse_body(AppointmentCreate))
    location = url_for("appointments.get_appointment", appointment_id=appointment.id)
    return appointment.to_dict(), 201, {"Location": location}


@bp.get("")
def list_appointments():
    raw_status = request.args.get("status")
    try:
        status = AppointmentStatus(raw_status) if raw_status else None
    except ValueError as exc:
        options = ", ".join(s.value for s in AppointmentStatus)
        raise BadRequestError(f"Status inválido. Use um destes: {options}.") from exc

    limit, offset = pagination()
    page = AppointmentRepository(get_db()).list(
        doctor_id=query_int("doctor_id", minimum=1),
        patient_id=query_int("patient_id", minimum=1),
        day=query_date("date"),
        status=status,
        limit=limit,
        offset=offset,
    )
    return page.to_dict()


@bp.get("/<int:appointment_id>")
def get_appointment(appointment_id: int):
    appointment = AppointmentRepository(get_db()).get(appointment_id)
    if appointment is None:
        raise NotFoundError("Consulta não encontrada.")
    return appointment.to_dict()


@bp.post("/<int:appointment_id>/cancel")
def cancel_appointment(appointment_id: int):
    return _service().cancel(appointment_id).to_dict()


@bp.post("/<int:appointment_id>/complete")
def complete_appointment(appointment_id: int):
    return _service().complete(appointment_id).to_dict()
