"""Modelo de Usuário — pessoa que abre denúncias no sistema."""

from datetime import datetime, timezone
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, EmailStr, Field, field_validator


class User(Document):
    """Representa um cidadão cadastrado no sistema de denúncias."""

    nome: str = Field(..., min_length=3, max_length=120)
    email: Indexed(EmailStr, unique=True)  # type: ignore[valid-type]
    cpf: Indexed(str, unique=True)  # type: ignore[valid-type]
    telefone: Optional[str] = None
    ativo: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"
        indexes = [
            [("nome", 1)],
        ]


# ---------------------------------------------------------------------------
# Schemas Pydantic auxiliares (request / response)
# ---------------------------------------------------------------------------

class UserIn(BaseModel):
    """Payload para criar ou atualizar um usuário."""

    nome: str = Field(..., min_length=3, max_length=120)
    email: EmailStr
    cpf: str = Field(..., pattern=r"^\d{11}$")
    telefone: Optional[str] = None


class UserOut(BaseModel):
    """Representação pública de um usuário (sem dados sensíveis)."""

    id: str
    nome: str
    email: str
    telefone: Optional[str]
    ativo: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)
