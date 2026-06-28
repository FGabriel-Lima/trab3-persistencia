"""Modelo de Denúncia — entidade central do sistema."""

from datetime import datetime, timezone
from typing import List, Optional

from beanie import BackLink, Document, Link, PydanticObjectId
from pydantic import BaseModel, Field, field_validator

from app.models.category import Category
from app.models.complaint_status import ComplaintStatus
from app.models.documento import Documento
from app.models.location import Location
from app.models.user import User


class Complaint(Document):
    """
    Denúncia urbana registrada por um cidadão.

    Relacionamentos:
    - usuario (Many-to-One) → User
    - categoria (Many-to-One) → Category
    - status (Many-to-One) → ComplaintStatus
    - localizacao (embedded) → Location
    - atendimentos (Many-to-Many via referência) → ServiceResponse
    - documentos (One-to-Many via BackLink) → Documento
    """

    titulo: str = Field(..., min_length=5, max_length=200)
    descricao: str = Field(..., min_length=10)
    usuario: Link[User]
    categoria: Link[Category]
    status: Link[ComplaintStatus]
    localizacao: Location  # documento embutido
    prioridade: int = Field(default=1, ge=1, le=5)  # 1 = baixa … 5 = crítica
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Many-to-Many com ServiceResponse — a lista de IDs fica aqui
    atendimentos: List[Link["ServiceResponse"]] = Field(default_factory=list)  # type: ignore[type-arg]

    # BackLink para recuperar documentos associados (1:N inverso)
    # original_field deve estar em json_schema_extra para o Beanie 1.26 encontrar
    documentos: Optional[List[BackLink[Documento]]] = Field(
        default=None, json_schema_extra={"original_field": "denuncia"}
    )

    class Settings:
        name = "complaints"
        indexes = [
            [("usuario.$id", 1)],
            [("categoria.$id", 1)],
            [("status.$id", 1)],
            [("localizacao.bairro", 1)],
            [("created_at", -1)],
            [("titulo", "text"), ("descricao", "text")],  # índice full-text
        ]


# ---------------------------------------------------------------------------
# Schemas auxiliares
# ---------------------------------------------------------------------------

class ComplaintIn(BaseModel):
    """Payload para criação de uma nova denúncia."""

    titulo: str = Field(..., min_length=5, max_length=200)
    descricao: str = Field(..., min_length=10)
    usuario_id: PydanticObjectId
    categoria_id: PydanticObjectId
    status_id: PydanticObjectId
    localizacao: Location
    prioridade: int = Field(default=1, ge=1, le=5)


class ComplaintUpdate(BaseModel):
    """Payload parcial para atualizar uma denúncia existente."""

    titulo: Optional[str] = Field(default=None, min_length=5, max_length=200)
    descricao: Optional[str] = Field(default=None, min_length=10)
    categoria_id: Optional[PydanticObjectId] = None
    status_id: Optional[PydanticObjectId] = None
    localizacao: Optional[Location] = None
    prioridade: Optional[int] = Field(default=None, ge=1, le=5)


class ComplaintOut(BaseModel):
    """Representação resumida de uma denúncia para listagens."""

    id: str
    titulo: str
    descricao: str
    prioridade: int
    localizacao: Location
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)


class ComplaintDetailOut(BaseModel):
    """Representação completa de uma denúncia com relacionamentos resolvidos."""

    id: str
    titulo: str
    descricao: str
    prioridade: int
    localizacao: Location
    usuario_id: Optional[str]
    usuario_nome: Optional[str]
    categoria_id: Optional[str]
    categoria_nome: Optional[str]
    status_id: Optional[str]
    status_nome: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)


# evita ciclo de importação com ServiceResponse
from app.models.service_response import ServiceResponse  # noqa: E402, F401

# Complaint está definida agora — resolve a forward ref em Documento
Documento.model_rebuild(_types_namespace={"Complaint": Complaint})
