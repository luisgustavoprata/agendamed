"""Rotas de prontuário, prescrições, financeiro, repasse, estoque e relatórios.

Nesta versão não há perfis de acesso: toda a equipe logada usa todas as telas,
inclusive prontuários.
"""

from datetime import date, timedelta

from flask import Blueprint, g, request

from agendamed.db import get_db
from agendamed.errors import BadRequestError, BusinessRuleError
from agendamed.gestao import (
    AppointmentCharge,
    ClinicalSummaryUpdate,
    FinanceAccountCreate,
    CLINIC_ID,
    Gestao,
    GestaoDb,
    HealthPlanCreate,
    PayoutRuleSet,
    PrescriptionCreate,
    ProcedureCreate,
    RecordEntryCreate,
    StockItemCreate,
    StockItemUpdate,
    StockMovementCreate,
    TransactionCreate,
    TransactionPay,
    TransactionUpdate,
)
from agendamed.routes._helpers import now, parse_body, query_date, query_int, require_auth

bp = Blueprint("gestao", __name__)

CLINICAL = FINANCE = OWNER = ()


def current_user():
    return g.user


def _g() -> Gestao:
    return Gestao(GestaoDb(get_db()), CLINIC_ID)


def _today() -> str:
    return now().date().isoformat()


def _now() -> str:
    return now().replace(microsecond=0).isoformat(timespec="seconds")


def _period() -> tuple[date, date]:
    """Período das telas: ?start=&end= (padrão: o mês atual)."""
    today = now().date()
    start = query_date("start") or today.replace(day=1)
    end = query_date("end") or (start.replace(day=28) + timedelta(days=4)).replace(
        day=1
    ) - timedelta(days=1)
    if end < start:
        raise BadRequestError("A data final deve ser depois da inicial.")
    if (end - start).days > 366:
        raise BadRequestError("Escolha um período de até um ano.")
    return start, end


def _auth(*_roles) -> None:
    require_auth()


def _author_doctor(requested: int | None, gestao: Gestao, *, required: bool) -> int | None:
    """Médico responsável pelo registro (escolhido na tela)."""
    if requested is None:
        if required:
            raise BusinessRuleError("Escolha o médico que assina.")
        return None
    gestao.require_doctor(requested)
    return requested


# ------------------------------------------------------------------ prontuário


@bp.get("/patients/<int:patient_id>/record")
def get_record(patient_id: int):
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
    _auth(*CLINICAL)
    g = _g()
    g.require_patient(patient_id)
    data = parse_body(ClinicalSummaryUpdate)
    return g.save_clinical_summary(patient_id, data, current_user().id, _now())


@bp.post("/patients/<int:patient_id>/record/entries")
def add_entry(patient_id: int):
    _auth(*CLINICAL)
    g = _g()
    g.require_patient(patient_id)
    data = parse_body(RecordEntryCreate)
    doctor_id = _author_doctor(data.doctor_id, g, required=False)
    return g.add_record_entry(patient_id, data, doctor_id, current_user().id, _now()), 201


# ------------------------------------------------------------------ prescrições


@bp.get("/patients/<int:patient_id>/prescriptions")
def list_prescriptions(patient_id: int):
    _auth(*CLINICAL)
    g = _g()
    g.require_patient(patient_id)
    return {"items": g.prescriptions(patient_id)}


@bp.post("/patients/<int:patient_id>/prescriptions")
def add_prescription(patient_id: int):
    _auth(*CLINICAL)
    g = _g()
    g.require_patient(patient_id)
    data = parse_body(PrescriptionCreate)
    doctor_id = _author_doctor(data.doctor_id, g, required=True)
    return g.add_prescription(patient_id, data, doctor_id, current_user().id, _now()), 201


@bp.get("/prescriptions/<int:prescription_id>")
def get_prescription(prescription_id: int):
    _auth(*CLINICAL)
    return _g().prescription(prescription_id)


# ------------------------------------------------------------------ procedimentos e convênios


@bp.get("/procedures")
def list_procedures():
    require_auth()
    return {"items": _g().procedures(only_active=request.args.get("active") == "1")}


@bp.post("/procedures")
def create_procedure():
    _auth(*OWNER)
    return _g().save_procedure(parse_body(ProcedureCreate)), 201


@bp.put("/procedures/<int:procedure_id>")
def update_procedure(procedure_id: int):
    _auth(*OWNER)
    return _g().save_procedure(parse_body(ProcedureCreate), procedure_id)


@bp.get("/health-plans")
def list_health_plans():
    require_auth()
    return {"items": _g().health_plans(only_active=request.args.get("active") == "1")}


@bp.post("/health-plans")
def create_health_plan():
    _auth(*OWNER)
    return _g().save_health_plan(parse_body(HealthPlanCreate)), 201


@bp.put("/health-plans/<int:plan_id>")
def update_health_plan(plan_id: int):
    _auth(*OWNER)
    return _g().save_health_plan(parse_body(HealthPlanCreate), plan_id)


# ------------------------------------------------------------------ financeiro


@bp.get("/finance/accounts")
def list_accounts():
    _auth(*FINANCE)
    return {"items": _g().accounts()}


@bp.post("/finance/accounts")
def create_account():
    _auth(*FINANCE)
    return _g().add_account(parse_body(FinanceAccountCreate)), 201


@bp.get("/finance/transactions")
def list_transactions():
    _auth(*FINANCE)
    start, end = _period()
    kind = request.args.get("kind") or None
    status = request.args.get("status") or None
    if kind not in (None, "income", "expense"):
        raise BadRequestError("O parâmetro 'kind' deve ser income ou expense.")
    if status not in (None, "paid", "open"):
        raise BadRequestError("O parâmetro 'status' deve ser paid ou open.")
    items = _g().transactions(
        start=start,
        end=end,
        today=_today(),
        kind=kind,
        status=status,
        account_id=query_int("account_id", minimum=1),
    )
    return {"items": items}


@bp.post("/finance/transactions")
def create_transaction():
    _auth(*FINANCE)
    return _g().add_transaction(parse_body(TransactionCreate), _today()), 201


@bp.patch("/finance/transactions/<int:tx_id>")
def update_transaction(tx_id: int):
    _auth(*FINANCE)
    return _g().update_transaction(tx_id, parse_body(TransactionUpdate), _today())


@bp.delete("/finance/transactions/<int:tx_id>")
def delete_transaction(tx_id: int):
    _auth(*FINANCE)
    _g().delete_transaction(tx_id, _today())
    return "", 204


@bp.post("/finance/transactions/<int:tx_id>/pay")
def pay_transaction(tx_id: int):
    _auth(*FINANCE)
    return _g().pay_transaction(tx_id, parse_body(TransactionPay), _today())


@bp.post("/finance/transactions/<int:tx_id>/unpay")
def unpay_transaction(tx_id: int):
    _auth(*FINANCE)
    return _g().unpay_transaction(tx_id, _today())


@bp.get("/finance/cashflow")
def cashflow():
    _auth(*FINANCE)
    start, end = _period()
    return _g().cashflow(start, end, _today())


@bp.get("/appointments/<int:appointment_id>/charge")
def get_charge(appointment_id: int):
    _auth(*FINANCE)
    g = _g()
    g.require_appointment(appointment_id)
    return {"charge": g.appointment_charge(appointment_id, _today())}


@bp.post("/appointments/<int:appointment_id>/charge")
def charge_appointment(appointment_id: int):
    _auth(*FINANCE)
    return _g().charge_appointment(appointment_id, parse_body(AppointmentCharge), _today()), 201


@bp.get("/finance/payout-rules")
def list_payout_rules():
    _auth(*OWNER)
    return {"items": _g().payout_rules()}


@bp.put("/finance/payout-rules")
def set_payout_rule():
    _auth(*OWNER)
    return {"items": _g().set_payout_rule(parse_body(PayoutRuleSet))}


@bp.delete("/finance/payout-rules/<int:rule_id>")
def delete_payout_rule(rule_id: int):
    _auth(*OWNER)
    _g().delete_payout_rule(rule_id)
    return "", 204


@bp.get("/finance/payouts")
def payouts():
    _auth(*OWNER)
    start, end = _period()
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "items": _g().payouts(start, end, _today()),
    }


@bp.get("/finance/tiss")
def tiss_batch():
    _auth(*FINANCE)
    plan_id = query_int("health_plan_id", minimum=1)
    if plan_id is None:
        raise BadRequestError("Escolha o convênio (health_plan_id).")
    start, end = _period()
    return _g().tiss_batch(plan_id, start, end, _today())


# ------------------------------------------------------------------ estoque


@bp.get("/stock/items")
def list_stock():
    _auth(*FINANCE)
    return {"items": _g().stock_items()}


@bp.post("/stock/items")
def create_stock_item():
    _auth(*FINANCE)
    return _g().add_stock_item(parse_body(StockItemCreate)), 201


@bp.patch("/stock/items/<int:item_id>")
def update_stock_item(item_id: int):
    _auth(*FINANCE)
    return _g().update_stock_item(item_id, parse_body(StockItemUpdate))


@bp.get("/stock/items/<int:item_id>/movements")
def stock_movements(item_id: int):
    _auth(*FINANCE)
    return {"items": _g().stock_movements(item_id)}


@bp.post("/stock/items/<int:item_id>/movements")
def move_stock(item_id: int):
    _auth(*FINANCE)
    return _g().move_stock(item_id, parse_body(StockMovementCreate), current_user().id, _now()), 201


# ------------------------------------------------------------------ relatórios


@bp.get("/reports/overview")
def overview():
    _auth(*OWNER)
    start, end = _period()
    return _g().overview(start, end, _today())
