"""Cada prueba corre dentro de una transacción que se deshace al terminar."""

from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from porteria_api.db import SessionDep
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db

MARCA = "prueba-aislamiento"
INSERTAR = text("INSERT INTO alembic_version (version_num) VALUES (:v)")
CONTAR = text("SELECT count(*) FROM alembic_version WHERE version_num = :v")


# Dos corridas: la segunda solo pasa si la primera no dejó su fila en la base.
@pytest.mark.parametrize("corrida", [1, 2])
def test_lo_que_escribe_una_prueba_no_lo_ve_la_siguiente(db_session: Session, corrida: int) -> None:
    assert db_session.scalar(CONTAR, {"v": MARCA}) == 0

    db_session.execute(INSERTAR, {"v": MARCA})
    db_session.commit()  # con create_savepoint, commit solo libera el savepoint

    assert db_session.scalar(CONTAR, {"v": MARCA}) == 1


def test_las_peticiones_usan_la_sesion_de_la_prueba(
    client: TestClient, db_session: Session
) -> None:
    db_session.execute(INSERTAR, {"v": MARCA})
    app = cast(FastAPI, client.app)

    @app.get("/_prueba/versiones")
    def versiones(session: SessionDep) -> int:
        return session.scalar(CONTAR, {"v": MARCA}) or 0

    response = client.get("/_prueba/versiones")

    assert response.json() == 1
