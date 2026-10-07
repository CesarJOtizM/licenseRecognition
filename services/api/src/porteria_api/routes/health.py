"""Chequeo de salud: indica si la API está viva y si llega a la base de datos."""

import logging
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from porteria_api.db import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["ok", "unavailable"]


@router.get(
    "/health",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
def health(session: SessionDep, response: Response) -> HealthResponse:
    try:
        session.execute(text("SELECT 1"))
    except OperationalError:
        # El detalle va al log; el cliente solo ve "unavailable".
        logger.warning("Base de datos no disponible para /health", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="error", database="unavailable")
    return HealthResponse(status="ok", database="ok")
