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
    # Solo HMAC: así un token firmado con "none" o con llave pública nunca se acepta.
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_minutes: int = Field(default=30, ge=1, le=1440)
