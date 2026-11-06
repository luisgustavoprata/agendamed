"""Rotas dos cadastros: procedimentos e convênios."""

from flask import request

from agendamed.gestao.schemas import HealthPlanCreate, ProcedureCreate
from agendamed.routes._helpers import parse_body, require_auth
from agendamed.routes.gestao._comum import OWNER, _auth, _g, bp


@bp.get("/procedures")
def list_procedures():
    """GET /procedures — os procedimentos (?active=1: só os ativos)."""
    require_auth()
    return {"items": _g().procedures(only_active=request.args.get("active") == "1")}


@bp.post("/procedures")
def create_procedure():
    """POST /procedures — cria um procedimento."""
    _auth(*OWNER)
    return _g().save_procedure(parse_body(ProcedureCreate)), 201


@bp.put("/procedures/<int:procedure_id>")
def update_procedure(procedure_id: int):
    """PUT /procedures/<id> — altera um procedimento."""
    _auth(*OWNER)
    return _g().save_procedure(parse_body(ProcedureCreate), procedure_id)


@bp.get("/health-plans")
def list_health_plans():
    """GET /health-plans — os convênios (?active=1: só os ativos)."""
    require_auth()
    return {"items": _g().health_plans(only_active=request.args.get("active") == "1")}


@bp.post("/health-plans")
def create_health_plan():
    """POST /health-plans — cria um convênio."""
    _auth(*OWNER)
    return _g().save_health_plan(parse_body(HealthPlanCreate)), 201


@bp.put("/health-plans/<int:plan_id>")
def update_health_plan(plan_id: int):
    """PUT /health-plans/<id> — altera um convênio."""
    _auth(*OWNER)
    return _g().save_health_plan(parse_body(HealthPlanCreate), plan_id)
