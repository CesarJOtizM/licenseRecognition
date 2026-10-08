"""Configuración de la API, leída de variables de entorno."""

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://porteria:porteria@127.0.0.1:5432/porteria"


class DatabaseSettings(BaseSettings):
    """Cada campo se puede cambiar con la variable de entorno del mismo nombre en mayúsculas.

    Alembic y el CLI solo necesitan esta parte: no exigen JWT_SECRET.
    """

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = DEFAULT_DATABASE_URL
    db_connect_timeout: int = Field(default=3, ge=1)


class Settings(DatabaseSettings):
    """Configuración completa de la API; sin JWT_SECRET no arranca."""

    jwt_secret: SecretStr = Field(min_length=32)
    # Solo HS256: un token "none" o de llave pública nunca se acepta, y los 32 caracteres del
    # secreto alcanzan (HS384/HS512 piden 48/64).
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_minutes: int = Field(default=30, ge=1, le=1440)
