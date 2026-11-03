from flask import Blueprint, current_app, g, request

from agendamed.db import get_db
from agendamed.errors import ForbiddenError, TooManyRequestsError, UnauthorizedError
from agendamed.repositories import UserRepository
from agendamed.routes._helpers import now, parse_body, require_auth
from agendamed.schemas import LoginRequest, UserCreate
from agendamed.security import create_access_token, hash_password, verify_password

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _limiter():
    return current_app.extensions["login_limiter"]


def _ip_limiter():
    return current_app.extensions["login_ip_limiter"]


def _dummy_hash() -> str:
    """Hash descartável, usado quando o e-mail não existe (calculado uma vez por processo)."""
    cached = current_app.extensions.get("login_dummy_hash")
    if cached is None:
        cached = hash_password("senha-inexistente", current_app.config["PASSWORD_HASH_ITERATIONS"])
        current_app.extensions["login_dummy_hash"] = cached
    return cached


def _too_many(wait: int) -> TooManyRequestsError:
    minutes = max(1, round(wait / 60))
    return TooManyRequestsError(
        f"Muitas tentativas de login. Tente novamente em cerca de {minutes} min.",
        headers={"Retry-After": str(wait)},
    )


@bp.post("/register")
def register():
    if not current_app.config["ALLOW_SIGNUP"]:
        raise ForbiddenError("O cadastro de novas contas está fechado.")
    data = parse_body(UserCreate)
    password_hash = hash_password(data.password, current_app.config["PASSWORD_HASH_ITERATIONS"])
    user = UserRepository(get_db()).create(data.email, data.full_name, password_hash)
    return user.to_dict(), 201


@bp.post("/login")
def login():
    data = parse_body(LoginRequest)

    # A chave combina IP e e-mail: um atacante não consegue bloquear a conta de outra
    # pessoa a partir do próprio IP, e também não pode testar senhas sem limite.
    key = f"{request.remote_addr}|{data.email}"
    ip_key = request.remote_addr or ""
    timestamp = now().timestamp()
    wait = _ip_limiter().retry_after(ip_key, timestamp) or _limiter().retry_after(key, timestamp)
    if wait is not None:
        raise _too_many(wait)

    user = UserRepository(get_db()).get_by_email(data.email)
    # A mesma mensagem e o mesmo tempo de resposta (o hash é calculado mesmo quando o
    # e-mail não existe) não revelam quais e-mails estão cadastrados.
    stored_hash = user.password_hash if user else _dummy_hash()
    password_ok = verify_password(data.password, stored_hash)
    if user is None or not password_ok:
        _limiter().register_failure(key, timestamp)
        _ip_limiter().register_failure(ip_key, timestamp)
        raise UnauthorizedError("E-mail ou senha incorretos.")

    _limiter().reset(key)
    expires = current_app.config["TOKEN_EXPIRES_MINUTES"]
    token = create_access_token(user.id, current_app.config["SECRET_KEY"], expires)
    return {"access_token": token, "token_type": "bearer", "expires_in": expires * 60}


@bp.get("/me")
def me():
    require_auth()
    return g.user.to_dict()
