"""Configuración de la API, leída de variables de entorno."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://porteria:porteria@127.0.0.1:5432/porteria"


class Settings(BaseSettings):
    """Cada campo se puede cambiar con la variable de entorno del mismo nombre en mayúsculas."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = DEFAULT_DATABASE_URL
    db_connect_timeout: int = Field(default=3, ge=1)
