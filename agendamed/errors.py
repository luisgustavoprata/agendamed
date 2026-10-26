"""Erros de domínio e tradução de exceções para respostas JSON padronizadas."""

from flask import Flask
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException


class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str, headers: dict | None = None):
        super().__init__(message)
        self.message = message
        self.headers = headers or {}


class BadRequestError(DomainError):
    status_code = 400


class UnauthorizedError(DomainError):
    status_code = 401


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


class BusinessRuleError(DomainError):
    status_code = 422


class TooManyRequestsError(DomainError):
    status_code = 429


HTTP_MESSAGES = {
    404: "Rota não encontrada.",
    405: "Método HTTP não permitido nesta rota.",
    415: "Envie o corpo da requisição como JSON.",
}


# Mensagens do Pydantic traduzidas pelo tipo do erro. `{...}` usa o contexto do erro.
VALIDATION_MESSAGES = {
    "missing": "Campo obrigatório.",
    "extra_forbidden": "Campo não permitido.",
    "string_type": "Informe um texto.",
    "string_too_short": "Use pelo menos {min_length} caracteres.",
    "string_too_long": "Use no máximo {max_length} caracteres.",
    "string_pattern_mismatch": "Formato inválido.",
    "int_parsing": "Informe um número inteiro.",
    "int_type": "Informe um número inteiro.",
    "greater_than": "O valor deve ser maior que {gt}.",
    "greater_than_equal": "O valor deve ser no mínimo {ge}.",
    "less_than_equal": "O valor deve ser no máximo {le}.",
    "date_parsing": "Data inválida. Use o formato AAAA-MM-DD.",
    "date_from_datetime_parsing": "Data inválida. Use o formato AAAA-MM-DD.",
    "time_parsing": "Horário inválido. Use o formato HH:MM.",
    "datetime_parsing": "Data e hora inválidas. Use o formato AAAA-MM-DDTHH:MM.",
    "datetime_from_date_parsing": "Data e hora inválidas. Use o formato AAAA-MM-DDTHH:MM.",
    "timezone_naive": "Informe o horário local, sem fuso horário.",
}


def _translate(err: dict) -> str:
    template = VALIDATION_MESSAGES.get(err["type"])
    if template is None:
        return err["msg"].removeprefix("Value error, ")
    try:
        return template.format(**err.get("ctx", {}))
    except (KeyError, IndexError):
        return err["msg"]


def _format_validation_error(exc: ValidationError) -> list[dict]:
    errors = []
    for err in exc.errors():
        field = ".".join(str(part) for part in err["loc"]) or "body"
        errors.append({"field": field, "message": _translate(err)})
    return errors


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(DomainError)
    def handle_domain_error(exc: DomainError):
        return {"detail": exc.message}, exc.status_code, exc.headers

    @app.errorhandler(ValidationError)
    def handle_validation_error(exc: ValidationError):
        return {"detail": "Dados inválidos.", "errors": _format_validation_error(exc)}, 422

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        return {"detail": HTTP_MESSAGES.get(exc.code, exc.description)}, exc.code
