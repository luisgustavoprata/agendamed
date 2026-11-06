"""Peças usadas por todas as rotas da gestão: o blueprint, os perfis e os ajudantes.

`bp` é o blueprint único da gestão. Cada arquivo deste pacote registra as suas rotas
nele, e o `__init__.py` importa todos para que as rotas existam.
"""

from datetime import date, timedelta

from flask import Blueprint, g

from agendamed.db import get_db
from agendamed.errors import BadRequestError, BusinessRuleError
from agendamed.gestao import CLINIC_ID, Gestao, GestaoDb
from agendamed.routes._helpers import now, query_date, require_auth

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
