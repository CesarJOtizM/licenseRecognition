"""Hash de contraseñas (Argon2id) y tokens de acceso (JWT). No depende de FastAPI."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pydantic import SecretStr

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
REQUIRED_CLAIMS = ["sub", "ver", "iat", "exp"]


class Passwords:
    """Calcula y verifica hashes; las pruebas inyectan un `PasswordHash` con parámetros baratos."""

    def __init__(self, hasher: PasswordHash | None = None) -> None:
        self._hasher = hasher or PasswordHash((Argon2Hasher(),))
        self._dummy_hash = self._hasher.hash("contrasena-de-relleno")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        return self._hasher.verify(password, hashed)

    def verify_dummy(self, password: str) -> None:
        """Gasta lo mismo que un `verify` real: un usuario inexistente no responde más rápido."""
        self._hasher.verify(password, self._dummy_hash)


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    token_version: int


def encode_access_token(
    user_id: UUID,
    token_version: int,
    *,
    secret: SecretStr,
    algorithm: str,
    minutes: int,
    now: datetime,
) -> str:
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, secret.get_secret_value(), algorithm=algorithm)


def decode_access_token(
    token: str,
    *,
    secret: SecretStr,
    algorithm: str,
    now: datetime | None = None,
) -> TokenClaims:
    """Valida firma, algoritmo y vencimiento; lanza `jwt.InvalidTokenError` si algo falla."""
    payload = jwt.decode(
        token,
        secret.get_secret_value(),
        algorithms=[algorithm],
        # El vencimiento se revisa abajo contra `now`: PyJWT solo conoce el reloj del sistema.
        options={"require": REQUIRED_CLAIMS, "verify_exp": False},
    )
    if payload["exp"] <= (now or datetime.now(UTC)).timestamp():
        raise jwt.ExpiredSignatureError("Signature has expired")
    # bool es subclase de int: `True` no es una versión válida.
    if type(payload["ver"]) is not int:
        raise jwt.InvalidTokenError("ver must be an integer")
    try:
        user_id = UUID(payload["sub"])
    except ValueError as exc:
        raise jwt.InvalidTokenError("sub must be a UUID") from exc
    return TokenClaims(user_id=user_id, token_version=payload["ver"])
