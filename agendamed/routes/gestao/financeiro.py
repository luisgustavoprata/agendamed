"""Rotas do financeiro: contas, lançamentos, faturamento das consultas, repasse e guias."""

from flask import request

from agendamed.errors import BadRequestError
from agendamed.gestao.schemas import (
    AppointmentCharge,
    FinanceAccountCreate,
    PayoutRuleSet,
    TransactionCreate,
    TransactionPay,
    TransactionUpdate,
)
from agendamed.routes._helpers import parse_body, query_int
from agendamed.routes.gestao._comum import FINANCE, OWNER, _auth, _g, _period, _today, bp


@bp.get("/finance/accounts")
def list_accounts():
    """GET /finance/accounts — as contas com o saldo."""
    _auth(*FINANCE)
    return {"items": _g().accounts()}


@bp.post("/finance/accounts")
def create_account():
    """POST /finance/accounts — cria uma conta."""
    _auth(*FINANCE)
    return _g().add_account(parse_body(FinanceAccountCreate)), 201


@bp.get("/finance/transactions")
def list_transactions():
    """GET /finance/transactions — lançamentos do período (?start=&end=), com filtros por tipo,
    situação e conta.
    """
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
    """POST /finance/transactions — cria um lançamento."""
    _auth(*FINANCE)
    return _g().add_transaction(parse_body(TransactionCreate), _today()), 201


@bp.patch("/finance/transactions/<int:tx_id>")
def update_transaction(tx_id: int):
    """PATCH /finance/transactions/<id> — altera um lançamento."""
    _auth(*FINANCE)
    return _g().update_transaction(tx_id, parse_body(TransactionUpdate), _today())


@bp.delete("/finance/transactions/<int:tx_id>")
def delete_transaction(tx_id: int):
    """DELETE /finance/transactions/<id> — apaga um lançamento em aberto."""
    _auth(*FINANCE)
    _g().delete_transaction(tx_id, _today())
    return "", 204


@bp.post("/finance/transactions/<int:tx_id>/pay")
def pay_transaction(tx_id: int):
    """POST /finance/transactions/<id>/pay — registra o pagamento."""
    _auth(*FINANCE)
    return _g().pay_transaction(tx_id, parse_body(TransactionPay), _today())


@bp.post("/finance/transactions/<int:tx_id>/unpay")
def unpay_transaction(tx_id: int):
    """POST /finance/transactions/<id>/unpay — desfaz o pagamento."""
    _auth(*FINANCE)
    return _g().unpay_transaction(tx_id, _today())


@bp.get("/finance/cashflow")
def cashflow():
    """GET /finance/cashflow — fluxo de caixa do período."""
    _auth(*FINANCE)
    start, end = _period()
    return _g().cashflow(start, end, _today())


@bp.get("/appointments/<int:appointment_id>/charge")
def get_charge(appointment_id: int):
    """GET /appointments/<id>/charge — a cobrança da consulta, se houver."""
    _auth(*FINANCE)
    g = _g()
    g.require_appointment(appointment_id)
    return {"charge": g.appointment_charge(appointment_id, _today())}


@bp.post("/appointments/<int:appointment_id>/charge")
def charge_appointment(appointment_id: int):
    """POST /appointments/<id>/charge — fatura a consulta."""
    _auth(*FINANCE)
    return _g().charge_appointment(appointment_id, parse_body(AppointmentCharge), _today()), 201


@bp.get("/finance/payout-rules")
def list_payout_rules():
    """GET /finance/payout-rules — as regras de repasse."""
    _auth(*OWNER)
    return {"items": _g().payout_rules()}


@bp.put("/finance/payout-rules")
def set_payout_rule():
    """PUT /finance/payout-rules — cria ou troca uma regra de repasse."""
    _auth(*OWNER)
    return {"items": _g().set_payout_rule(parse_body(PayoutRuleSet))}


@bp.delete("/finance/payout-rules/<int:rule_id>")
def delete_payout_rule(rule_id: int):
    """DELETE /finance/payout-rules/<id> — apaga uma regra de repasse."""
    _auth(*OWNER)
    _g().delete_payout_rule(rule_id)
    return "", 204


@bp.get("/finance/payouts")
def payouts():
    """GET /finance/payouts — o repasse de cada médico no período."""
    _auth(*OWNER)
    start, end = _period()
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "items": _g().payouts(start, end, _today()),
    }


@bp.get("/finance/tiss")
def tiss_batch():
    """GET /finance/tiss?health_plan_id= — guias de um convênio no período, para imprimir."""
    _auth(*FINANCE)
    plan_id = query_int("health_plan_id", minimum=1)
    if plan_id is None:
        raise BadRequestError("Escolha o convênio (health_plan_id).")
    start, end = _period()
    return _g().tiss_batch(plan_id, start, end, _today())
