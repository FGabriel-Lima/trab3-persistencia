"""Modelo de Status de Denúncia — ciclo de vida de uma denúncia."""

from beanie import Document, Indexed
from pydantic import BaseModel, Field, field_validator


STATUSES_PADRAO = ["Aberto", "Em Análise", "Em Atendimento", "Resolvido", "Arquivado"]


class ComplaintStatus(Document):
    """
    Estado atual de uma denúncia no fluxo de atendimento.

    Exemplos: Aberto, Em Análise, Resolvido.
    """

    nome: Indexed(str, unique=True)  # type: ignore[valid-type]
    descricao: str = ""
    ordem: int = Field(default=0, ge=0)  # para ordenar o fluxo na UI

    class Settings:
        name = "complaint_statuses"


class ComplaintStatusIn(BaseModel):
    """Payload para criar ou atualizar um status."""

    nome: str = Field(..., min_length=3, max_length=60)
    descricao: str = ""
    ordem: int = Field(default=0, ge=0)


class ComplaintStatusOut(BaseModel):
    """Representação pública de um status."""

    id: str
    nome: str
    descricao: str
    ordem: int

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)
