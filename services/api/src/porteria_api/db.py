"""Motor de SQLAlchemy y sesión por petición."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from porteria_api.config import Settings


def create_db_engine(settings: Settings) -> Engine:
    """Crea el motor sin conectarse: la primera conexión se abre al usarlo."""
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.db_connect_timeout},
    )


def get_session(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.sessionmaker
    session = factory()
    try:
        yield session
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]
