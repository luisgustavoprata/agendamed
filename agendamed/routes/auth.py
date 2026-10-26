from flask import Blueprint, current_app, g, request

from agendamed.db import get_db
from agendamed.errors import TooManyRequestsError, UnauthorizedError
from agendamed.repositories import UserRepository
from agendamed.routes._helpers import now, parse_body, require_auth
from agendamed.schemas import LoginRequest, UserCreate
from agendamed.security import create_access_token, hash_password, verify_password

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _limiter():
    return current_app.extensions["login_limiter"]


@bp.post("/register")
def register():
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
    timestamp = now().timestamp()
    wait = _limiter().retry_after(key, timestamp)
    if wait is not None:
        minutes = max(1, round(wait / 60))
        raise TooManyRequestsError(
            f"Muitas tentativas de login. Tente novamente em cerca de {minutes} min.",
            headers={"Retry-After": str(wait)},
        )

    user = UserRepository(get_db()).get_by_email(data.email)
    # A mesma mensagem para e-mail inexistente e senha errada não revela
    # quais e-mails estão cadastrados.
    if user is None or not verify_password(data.password, user.password_hash):
        _limiter().register_failure(key, timestamp)
        raise UnauthorizedError("E-mail ou senha incorretos.")

    _limiter().reset(key)
    expires = current_app.config["TOKEN_EXPIRES_MINUTES"]
    token = create_access_token(user.id, current_app.config["SECRET_KEY"], expires)
    return {"access_token": token, "token_type": "bearer", "expires_in": expires * 60}


@bp.get("/me")
def me():
    require_auth()
    return g.user.to_dict()
