"""Erros de domínio e tradução de exceções para respostas JSON padronizadas."""

from flask import Flask
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException


class DomainError(Exception):
    """Erro de regra do sistema, que vira uma resposta JSON com status HTTP.

    Lance uma das subclasses abaixo (ex.: `raise NotFoundError("Paciente não encontrado.")`); o
    tratador em `register_error_handlers` monta a resposta `{"detail": "mensagem"}` com o status da
    classe.
    """

    status_code = 400

    def __init__(self, message: str, headers: dict | None = None):
        """Guarda a mensagem e cabeçalhos HTTP extras para a resposta (ex.: Retry-After)."""
        super().__init__(message)
        self.message = message
        self.headers = headers or {}


class BadRequestError(DomainError):
    """400: a requisição veio malformada (ex.: parâmetro inválido)."""

    status_code = 400


class UnauthorizedError(DomainError):
    """401: falta login, ou o token de acesso é inválido ou venceu."""

    status_code = 401


class ForbiddenError(DomainError):
    """403: a pessoa está logada, mas o perfil dela não permite a ação."""

    status_code = 403


class NotFoundError(DomainError):
    """404: o registro não existe (ou é de outra clínica)."""

    status_code = 404


class ConflictError(DomainError):
    """409: a ação conflita com o estado atual (ex.: horário já ocupado)."""

    status_code = 409


class BusinessRuleError(DomainError):
    """422: os dados estão no formato certo, mas quebram uma regra."""

    status_code = 422


class TooManyRequestsError(DomainError):
    """429: tentativas demais em pouco tempo; espere e tente de novo."""

    status_code = 429


HTTP_MESSAGES = {
    404: "Rota não encontrada.",
    405: "Método HTTP não permitido nesta rota.",
    413: "O corpo da requisição é grande demais.",
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
    """Mensagem em português para um erro de validação do Pydantic.

    Usa VALIDATION_MESSAGES pelo tipo do erro; sem tradução, aproveita a mensagem original, tirando
    o prefixo "Value error, ".
    """
    template = VALIDATION_MESSAGES.get(err["type"])
    if template is None:
        return err["msg"].removeprefix("Value error, ")
    try:
        return template.format(**err.get("ctx", {}))
    except (KeyError, IndexError):
        return err["msg"]


def _format_validation_error(exc: ValidationError) -> list[dict]:
    """Lista os erros de validação no formato da API: [{"field": ..., "message": ...}]."""
    errors = []
    for err in exc.errors():
        field = ".".join(str(part) for part in err["loc"]) or "body"
        errors.append({"field": field, "message": _translate(err)})
    return errors


def register_error_handlers(app: Flask) -> None:
    """Ensina o Flask a transformar erros em respostas JSON padronizadas.

    - DomainError (e subclasses): status da classe e a mensagem em "detail";
    - ValidationError do Pydantic: 422 com a lista de campos inválidos;
    - erros HTTP do Flask (404, 405, 413, 415...): mensagem em português.
    """

    @app.errorhandler(DomainError)
    def handle_domain_error(exc: DomainError):
        return {"detail": exc.message}, exc.status_code, exc.headers

    @app.errorhandler(ValidationError)
    def handle_validation_error(exc: ValidationError):
        return {"detail": "Dados inválidos.", "errors": _format_validation_error(exc)}, 422

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        return {"detail": HTTP_MESSAGES.get(exc.code, exc.description)}, exc.code
