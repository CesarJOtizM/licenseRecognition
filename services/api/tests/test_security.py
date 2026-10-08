from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
import pytest
from conftest import TEST_JWT_SECRET
from porteria_api.security import Passwords, TokenClaims, decode_access_token, encode_access_token
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pydantic import SecretStr

USER_ID = UUID("01900000-0000-7000-8000-000000000001")
ISSUED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
MINUTES = 30
SECRET = TEST_JWT_SECRET.get_secret_value()


class RecordingHash(PasswordHash):
    """Argon2 barato que anota cada verificación."""

    def __init__(self) -> None:
        super().__init__((Argon2Hasher(time_cost=1, memory_cost=8, parallelism=1),))
        self.verified: list[tuple[str | bytes, str | bytes]] = []

    def verify(self, password: str | bytes, hashed: str | bytes) -> bool:
        self.verified.append((password, hashed))
        return super().verify(password, hashed)


@pytest.fixture
def hasher() -> RecordingHash:
    return RecordingHash()


def issue(token_version: int = 0) -> str:
    return encode_access_token(
        USER_ID,
        token_version,
        secret=TEST_JWT_SECRET,
        algorithm="HS256",
        minutes=MINUTES,
        now=ISSUED_AT,
    )


def decode_at(token: str, now: datetime) -> TokenClaims:
    return decode_access_token(token, secret=TEST_JWT_SECRET, algorithm="HS256", now=now)


def forge(payload: dict[str, Any], key: str = SECRET, algorithm: str = "HS256") -> str:
    return jwt.encode(payload, key, algorithm=algorithm)


def valid_payload() -> dict[str, Any]:
    exp = ISSUED_AT + timedelta(minutes=MINUTES)
    return {"sub": str(USER_ID), "ver": 0, "iat": ISSUED_AT, "exp": exp}


def test_verify_acepta_solo_la_contrasena_original(hasher: RecordingHash) -> None:
    passwords = Passwords(hasher)

    hashed = passwords.hash("correcta-horse-battery")

    assert passwords.verify("correcta-horse-battery", hashed) is True
    assert passwords.verify("otra-contrasena-larga", hashed) is False


def test_dos_hashes_de_la_misma_contrasena_son_argon2id_distintos(hasher: RecordingHash) -> None:
    passwords = Passwords(hasher)

    first, second = passwords.hash("misma-contrasena"), passwords.hash("misma-contrasena")

    assert first != second
    assert first.startswith("$argon2id$")
    assert second.startswith("$argon2id$")
    assert "misma-contrasena" not in first
    assert "m=8,t=1,p=1" in first


def test_por_defecto_usa_los_parametros_recomendados_de_argon2() -> None:
    assert "m=65536,t=3,p=4" in Passwords().hash("contrasena-real")


def test_verify_dummy_verifica_contra_un_hash_de_relleno(hasher: RecordingHash) -> None:
    passwords = Passwords(hasher)
    hasher.verified.clear()

    passwords.verify_dummy("usuario-inexistente")

    assert len(hasher.verified) == 1
    checked, dummy_hash = hasher.verified[0]
    assert checked == "usuario-inexistente"
    assert str(dummy_hash).startswith("$argon2id$")


def test_el_token_lleva_sub_ver_iat_y_exp() -> None:
    payload = jwt.decode(
        issue(token_version=4), SECRET, algorithms=["HS256"], options={"verify_exp": False}
    )

    assert payload == {
        "sub": str(USER_ID),
        "ver": 4,
        "iat": int(ISSUED_AT.timestamp()),
        "exp": int((ISSUED_AT + timedelta(minutes=MINUTES)).timestamp()),
    }


def test_el_token_vale_hasta_un_segundo_antes_de_vencer() -> None:
    expires = ISSUED_AT + timedelta(minutes=MINUTES)

    claims = decode_at(issue(token_version=2), expires - timedelta(seconds=1))

    assert claims == TokenClaims(user_id=USER_ID, token_version=2)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_at(issue(), expires + timedelta(seconds=1))


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(
            forge(valid_payload(), key="otro-secreto-de-al-menos-32-caracteres"), id="otro-secreto"
        ),
        pytest.param(forge(valid_payload(), key="", algorithm="none"), id="alg-none"),
        pytest.param(forge(valid_payload(), key="x" * 64, algorithm="HS512"), id="otro-algoritmo"),
        pytest.param(forge(valid_payload() | {"sub": None}), id="sin-sub"),
        pytest.param(forge({k: v for k, v in valid_payload().items() if k != "ver"}), id="sin-ver"),
        pytest.param(forge(valid_payload() | {"sub": "no-es-uuid"}), id="sub-invalido"),
        pytest.param(forge(valid_payload() | {"ver": "0"}), id="ver-texto"),
        pytest.param(forge(valid_payload() | {"ver": True}), id="ver-booleano"),
        pytest.param("no.es.un-jwt", id="malformado"),
    ],
)
def test_tokens_invalidos_se_rechazan(token: str) -> None:
    with pytest.raises(jwt.InvalidTokenError):
        decode_at(token, ISSUED_AT + timedelta(minutes=1))


def test_sin_now_se_usa_la_hora_actual() -> None:
    token = encode_access_token(
        USER_ID, 0, secret=SecretStr(SECRET), algorithm="HS256", minutes=1, now=datetime.now(UTC)
    )

    assert decode_access_token(token, secret=TEST_JWT_SECRET, algorithm="HS256").user_id == USER_ID
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(issue(), secret=TEST_JWT_SECRET, algorithm="HS256")
