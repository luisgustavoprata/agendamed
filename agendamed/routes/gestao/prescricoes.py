"""Rotas das prescrições: receitas, atestados, pedidos de exame e relatórios médicos."""

from agendamed.gestao.schemas import PrescriptionCreate
from agendamed.routes._helpers import parse_body
from agendamed.routes.gestao._comum import (
    CLINICAL,
    _auth,
    _author_doctor,
    _g,
    _now,
    bp,
    current_user,
)


@bp.get("/patients/<int:patient_id>/prescriptions")
def list_prescriptions(patient_id: int):
    """GET /patients/<id>/prescriptions — os documentos do paciente."""
    _auth(*CLINICAL)
    g = _g()
    g.require_patient(patient_id)
    return {"items": g.prescriptions(patient_id)}


@bp.post("/patients/<int:patient_id>/prescriptions")
def add_prescription(patient_id: int):
    """POST /patients/<id>/prescriptions — cria um documento para o paciente."""
    _auth(*CLINICAL)
    g = _g()
    g.require_patient(patient_id)
    data = parse_body(PrescriptionCreate)
    doctor_id = _author_doctor(data.doctor_id, g, required=True)
    return g.add_prescription(patient_id, data, doctor_id, current_user().id, _now()), 201


@bp.get("/prescriptions/<int:prescription_id>")
def get_prescription(prescription_id: int):
    """GET /prescriptions/<id> — um documento."""
    _auth(*CLINICAL)
    return _g().prescription(prescription_id)
