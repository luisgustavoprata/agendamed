from flask import Blueprint, request, url_for

from agendamed.db import get_db
from agendamed.errors import NotFoundError
from agendamed.repositories import PatientRepository
from agendamed.routes._helpers import pagination, parse_body, require_auth
from agendamed.schemas import PatientCreate
from agendamed.validators import only_digits

bp = Blueprint("patients", __name__, url_prefix="/patients")
bp.before_request(require_auth)


@bp.post("")
def create_patient():
    patient = PatientRepository(get_db()).create(parse_body(PatientCreate))
    location = url_for("patients.get_patient", patient_id=patient.id)
    return patient.to_dict(), 201, {"Location": location}


@bp.get("")
def list_patients():
    limit, offset = pagination()
    search = request.args.get("q", "").strip()
    # Permite buscar pelo CPF com ou sem máscara.
    if search and only_digits(search) and not any(char.isalpha() for char in search):
        search = only_digits(search)
    page = PatientRepository(get_db()).list(search=search or None, limit=limit, offset=offset)
    return page.to_dict()


@bp.get("/<int:patient_id>")
def get_patient(patient_id: int):
    patient = PatientRepository(get_db()).get(patient_id)
    if patient is None:
        raise NotFoundError("Paciente não encontrado.")
    return patient.to_dict()
