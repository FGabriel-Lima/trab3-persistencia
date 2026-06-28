"""Dependências reutilizáveis injetadas nos endpoints via FastAPI DI."""

from typing import Annotated

from fastapi import Depends

from app.services.minio_service import MinioService


def get_minio_service() -> MinioService:
    """Fornece uma instância configurada do MinioService."""
    return MinioService()


MinioServiceDep = Annotated[MinioService, Depends(get_minio_service)]
