from flask import Blueprint, request, url_for

from agendamed.db import get_db
from agendamed.errors import NotFoundError
from agendamed.models import to_api_datetime
from agendamed.repositories import DoctorRepository
from agendamed.routes._helpers import now, pagination, parse_body, query_date, require_auth
from agendamed.schemas import DoctorCreate
from agendamed.services.appointments import AppointmentService

bp = Blueprint("doctors", __name__, url_prefix="/doctors")
bp.before_request(require_auth)


@bp.post("")
def create_doctor():
    doctor = DoctorRepository(get_db()).create(parse_body(DoctorCreate))
    location = url_for("doctors.get_doctor", doctor_id=doctor.id)
    return doctor.to_dict(), 201, {"Location": location}


@bp.get("")
def list_doctors():
    limit, offset = pagination()
    page = DoctorRepository(get_db()).list(
        specialty=request.args.get("specialty"), limit=limit, offset=offset
    )
    return page.to_dict()


@bp.get("/<int:doctor_id>")
def get_doctor(doctor_id: int):
    doctor = DoctorRepository(get_db()).get(doctor_id)
    if doctor is None:
        raise NotFoundError("Médico não encontrado.")
    return doctor.to_dict()


@bp.get("/<int:doctor_id>/availability")
def doctor_availability(doctor_id: int):
    day = query_date("date", required=True)
    slots = AppointmentService(get_db(), now()).availability(doctor_id, day)
    return {
        "doctor_id": doctor_id,
        "date": day.isoformat(),
        "available_slots": [to_api_datetime(slot) for slot in slots],
    }
