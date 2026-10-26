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
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{_ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
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
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> int:
    try:
        payload = jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token expirado. Faça login novamente.") from exc
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise UnauthorizedError("Token inválido.") from exc
