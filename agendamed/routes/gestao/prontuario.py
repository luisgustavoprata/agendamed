"""Rotas do prontuário: ficha clínica e registros."""

from agendamed.gestao.schemas import ClinicalSummaryUpdate, RecordEntryCreate
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


@bp.get("/patients/<int:patient_id>/record")
def get_record(patient_id: int):
    """GET /patients/<id>/record — o prontuário: dados do paciente, ficha clínica e registros."""
    _auth(*CLINICAL)
    g = _g()
    patient = g.require_patient(patient_id)
    return {
        "patient": patient,
        "summary": g.clinical_summary(patient_id),
        "entries": g.record_entries(patient_id),
    }


@bp.put("/patients/<int:patient_id>/record/summary")
def save_summary(patient_id: int):
    """PUT /patients/<id>/record/summary — grava a ficha clínica."""
    _auth(*CLINICAL)
    g = _g()
    g.require_patient(patient_id)
    data = parse_body(ClinicalSummaryUpdate)
    return g.save_clinical_summary(patient_id, data, current_user().id, _now())


@bp.post("/patients/<int:patient_id>/record/entries")
def add_entry(patient_id: int):
    """POST /patients/<id>/record/entries — acrescenta um registro ao prontuário."""
    _auth(*CLINICAL)
    g = _g()
    g.require_patient(patient_id)
    data = parse_body(RecordEntryCreate)
    doctor_id = _author_doctor(data.doctor_id, g, required=False)
    return g.add_record_entry(patient_id, data, doctor_id, current_user().id, _now()), 201
