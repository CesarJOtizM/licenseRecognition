"""Modelos de la base de datos.

Alembic compara contra `Base.metadata`: todo modelo nuevo se importa aquí para que lo vea.
"""

from porteria_api.models.base import Base

__all__ = ["Base"]
