"""`create-admin` sin base: argumentos, lectura de la contraseña y códigos de salida."""

import io
import runpy
import sys
from collections.abc import Callable

import pytest
from porteria_api.cli import EXIT_DB_UNAVAILABLE, EXIT_REJECTED, main

PASSWORD = "contrasena-del-admin"  # noqa: S105


def _prompt(*answers: str) -> tuple[Callable[[str], str], list[str]]:
    """Reemplaza a getpass: devuelve `answers` en orden y anota los mensajes que pidió."""
    prompts: list[str] = []
    pending = iter(answers)

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(pending)

    return read, prompts


@pytest.fixture(autouse=True)
def _base_inaccesible(monkeypatch: pytest.MonkeyPatch) -> None:
    # Si una prueba llegara a la base por error, saldría con EXIT_DB_UNAVAILABLE y no con 1.
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://porteria:porteria@127.0.0.1:1/x")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "1")
    monkeypatch.delenv("JWT_SECRET", raising=False)


def test_contrasenas_distintas_salen_sin_tocar_la_base(capsys: pytest.CaptureFixture[str]) -> None:
    read, prompts = _prompt(PASSWORD, PASSWORD + "x")

    code = main(["create-admin", "--username", "root"], read_password=read)

    assert code == EXIT_REJECTED
    assert len(prompts) == 2
    out, err = capsys.readouterr()
    assert "no coinciden" in err
    assert PASSWORD not in out + err


@pytest.mark.parametrize(
    ("username", "password", "field"),
    [
        ("root", "corta123", "password"),  # USR-08 S3: 8 caracteres
        ("root", "x" * 129, "password"),
        ("a b", PASSWORD, "username"),
        ("ab", PASSWORD, "username"),
    ],
)
def test_entrada_que_el_api_rechazaria_sale_con_error_y_sin_eco(
    capsys: pytest.CaptureFixture[str], username: str, password: str, field: str
) -> None:
    read, _ = _prompt(password, password)

    code = main(["create-admin", "--username", username], read_password=read)

    assert code == EXIT_REJECTED
    out, err = capsys.readouterr()
    assert f"{field}:" in err
    assert password not in out + err


def test_password_stdin_lee_una_linea_y_no_pregunta(capsys: pytest.CaptureFixture[str]) -> None:
    read, prompts = _prompt()

    code = main(
        ["create-admin", "--username", "root", "--password-stdin"],
        read_password=read,
        stdin=io.StringIO(PASSWORD + "\r\n"),
    )

    # La contraseña pasó la validación: falla recién al conectarse a la base.
    assert code == EXIT_DB_UNAVAILABLE
    assert prompts == []
    out, err = capsys.readouterr()
    assert "base de datos" in err
    assert PASSWORD not in out + err


def test_sin_username_es_un_error_de_uso() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["create-admin"])

    assert exc_info.value.code == 2


def test_se_ejecuta_como_modulo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["porteria_api.cli", "--help"])
    # Ya importado, runpy avisa con un RuntimeWarning que lo ejecuta dos veces.
    monkeypatch.delitem(sys.modules, "porteria_api.cli")

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("porteria_api.cli", run_name="__main__")

    assert exc_info.value.code == 0
