"""Modelo de Documento — metadados de arquivos armazenados no MinIO."""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from beanie import Document, Link
from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from app.models.complaint import Complaint  # pragma: no cover


class Documento(Document):
    """
    Metadados de um arquivo (foto/vídeo) vinculado a uma denúncia.

    O arquivo em si fica no MinIO; aqui guardamos apenas as informações
    necessárias para localizar, descrever e servir o arquivo.
    """

    # Campos obrigatórios conforme especificação
    original_filename: str
    content_type: str
    extension: str
    size_bytes: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Localização no MinIO
    bucket_name: str
    object_key: str  # caminho único dentro do bucket

    # Relacionamento 1:N com Denúncia
    denuncia: Link["Complaint"]  # type: ignore[type-arg]

    # Campos opcionais de metadados
    descricao: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "documentos"
        indexes = [
            [("denuncia.$id", 1)],
            [("created_at", -1)],
        ]


class DocumentoOut(BaseModel):
    """Representação pública de um documento (metadados)."""

    id: str
    original_filename: str
    content_type: str
    extension: str
    size_bytes: int
    created_at: datetime
    descricao: Optional[str]
    object_key: str

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)


class DocumentoUpdate(BaseModel):
    """Campos que podem ser atualizados em um documento."""

    descricao: Optional[str] = None
    original_filename: Optional[str] = None

