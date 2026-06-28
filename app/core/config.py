"""Configurações centrais da aplicação lidas a partir de variáveis de ambiente."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Agrega todas as variáveis de ambiente necessárias para a aplicação."""

    # API
    api_title: str = "Sistema de Denúncias Urbanas"
    api_version: str = "1.0.0"
    debug: bool = True

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "denuncias_urbanas"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "denuncias-bucket"
    minio_secure: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
