"""Configuração da API ORC (variáveis de ambiente)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./api/orc_dev.db"
    secret_key: str = "troque-esta-chave-em-producao"
    admin_username: str = "admin"
    admin_password: str = "orc-admin-change-me"
    seed_data_dir: str = "../dados_usuario"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    access_token_expire_minutes: int = 60 * 12
    algorithm: str = "HS256"


settings = Settings()
