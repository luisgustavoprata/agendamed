"""Hash de senhas (PBKDF2-HMAC-SHA256) e tokens de acesso JWT."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from agendamed.errors import UnauthorizedError

_ALGORITHM = "pbkdf2_sha256"
_JWT_ALGORITHM = "HS256"


def hash_password(password: str, iterations: int) -> str:
    """Gera o hash de uma senha para guardar no banco (nunca guarde a senha em si).

    Formato: `pbkdf2_sha256$<iterações>$<sal>$<resumo>`. O sal aleatório faz duas senhas iguais
    terem hashes diferentes.
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{_ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Confere se a senha digitada corresponde ao hash guardado.

    Refaz o cálculo com o mesmo sal e número de iterações e compara em tempo constante. Hash em
    formato desconhecido é tratado como senha errada.
    """
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$")
    except ValueError:
        return False
    if algorithm != _ALGORITHM:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
    )
    # Comparação em tempo constante evita ataques de temporização.
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_access_token(user_id: int, secret: str, expires_minutes: int) -> str:
    """Cria o token de acesso (JWT) entregue no login, com o id do usuário (`sub`) e a validade
    (`exp`). É assinado com a SECRET_KEY: sem ela, ninguém forja um token.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> int:
    """Devolve o id do usuário de um token válido; token vencido ou inválido vira erro 401."""
    try:
        payload = jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token expirado. Faça login novamente.") from exc
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise UnauthorizedError("Token inválido.") from exc
