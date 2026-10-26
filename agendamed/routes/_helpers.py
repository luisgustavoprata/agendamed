"""Utilitários compartilhados pelas rotas: leitura do corpo, query string e autenticação."""

from datetime import date, datetime

from flask import current_app, g, request
from pydantic import BaseModel

from agendamed.db import get_db
from agendamed.errors import BadRequestError, UnauthorizedError
from agendamed.repositories import UserRepository
from agendamed.security import decode_access_token

MAX_PAGE_SIZE = 100


def parse_body[SchemaT: BaseModel](schema: type[SchemaT]) -> SchemaT:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise BadRequestError("O corpo da requisição deve ser um objeto JSON.")
    return schema.model_validate(data)


def query_int(name: str, *, default: int | None = None, minimum: int = 0) -> int | None:
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise BadRequestError(f"O parâmetro '{name}' deve ser um número inteiro.") from exc
    if value < minimum:
        raise BadRequestError(f"O parâmetro '{name}' deve ser maior ou igual a {minimum}.")
    return value


def query_date(name: str, *, required: bool = False) -> date | None:
    raw = request.args.get(name)
    if raw is None:
        if required:
            raise BadRequestError(f"O parâmetro '{name}' é obrigatório (formato AAAA-MM-DD).")
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise BadRequestError(f"O parâmetro '{name}' deve estar no formato AAAA-MM-DD.") from exc


def pagination() -> tuple[int, int]:
    limit = min(query_int("limit", default=20, minimum=1), MAX_PAGE_SIZE)
    offset = query_int("offset", default=0)
    return limit, offset


def now() -> datetime:
    """Relógio injetável: os testes substituem `CLOCK` por um horário fixo."""
    return current_app.config["CLOCK"]()


def require_auth() -> None:
    """Valida o cabeçalho `Authorization: Bearer <token>` e guarda o usuário em `g.user`."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("Token de acesso ausente.")
    user_id = decode_access_token(token, current_app.config["SECRET_KEY"])
    user = UserRepository(get_db()).get(user_id)
    if user is None:
        raise UnauthorizedError("Usuário do token não existe mais.")
    g.user = user
