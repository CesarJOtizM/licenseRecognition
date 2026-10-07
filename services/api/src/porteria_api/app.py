"""Fábrica de la aplicación FastAPI.

Se ejecuta con: uvicorn porteria_api.app:create_app --factory
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from porteria_api import __version__
from porteria_api.config import Settings
from porteria_api.db import create_db_engine
from porteria_api.routes import health


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_db_engine(resolved)
        app.state.engine = engine
        app.state.sessionmaker = sessionmaker(engine)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Portería API", version=__version__, lifespan=lifespan)
    app.include_router(health.router)
    return app
