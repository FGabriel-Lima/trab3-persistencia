"""
Modelo de Atendimento — resposta/ação do poder público sobre denúncias.

Implementa o relacionamento Many-to-Many entre Atendimento e Denúncia:
- Um atendimento pode abranger várias denúncias (ex: uma equipe resolve
  múltiplos buracos na mesma rua em uma única ordem de serviço).
- Uma denúncia pode ter vários atendimentos ao longo do tempo.
"""

from datetime import datetime, timezone
from typing import List, Optional

from beanie import Document, Link
from pydantic import BaseModel, Field, field_validator


class ServiceResponse(Document):
    """
    Registro de atendimento a uma ou mais denúncias pelo poder público.

    O campo `denuncias` é a ponta Many da relação Many-to-Many com Complaint.
    """

    descricao: str = Field(..., min_length=10)
    responsavel: str = Field(..., min_length=3, max_length=120)  # nome do órgão/servidor
    orgao: Optional[str] = None  # ex: "SUBPREFEITURA SELAS", "SABESP"
    previsao_conclusao: Optional[datetime] = None
    concluido: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Many-to-Many: um atendimento referencia N denúncias
    denuncias: List[Link["Complaint"]] = Field(default_factory=list)  # type: ignore[type-arg]

    class Settings:
        name = "service_responses"
        indexes = [
            [("created_at", -1)],
            [("concluido", 1)],
        ]


class ServiceResponseIn(BaseModel):
    """Payload para criar um novo atendimento."""

    descricao: str = Field(..., min_length=10)
    responsavel: str = Field(..., min_length=3, max_length=120)
    orgao: Optional[str] = None
    previsao_conclusao: Optional[datetime] = None
    denuncia_ids: List[str] = Field(..., min_length=1)


class ServiceResponseUpdate(BaseModel):
    """Payload parcial para atualizar um atendimento."""

    descricao: Optional[str] = Field(default=None, min_length=10)
    responsavel: Optional[str] = None
    orgao: Optional[str] = None
    previsao_conclusao: Optional[datetime] = None
    concluido: Optional[bool] = None
    denuncia_ids: Optional[List[str]] = None


class ServiceResponseOut(BaseModel):
    """Representação pública de um atendimento."""

    id: str
    descricao: str
    responsavel: str
    orgao: Optional[str]
    concluido: bool
    previsao_conclusao: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)


# importação diferida para evitar ciclo circular
from app.models.complaint import Complaint  # noqa: E402, F401
