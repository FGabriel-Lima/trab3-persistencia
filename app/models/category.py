"""Modelo de Categoria — classifica o tipo de problema relatado na denúncia."""

from datetime import datetime, timezone
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field, field_validator


class Category(Document):
    """Categoria de denúncia (ex: Buraco na via, Iluminação pública)."""

    nome: Indexed(str, unique=True)  # type: ignore[valid-type]
    descricao: Optional[str] = None
    ativa: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "categories"


class CategoryIn(BaseModel):
    """Payload para criar ou atualizar uma categoria."""

    nome: str = Field(..., min_length=3, max_length=80)
    descricao: Optional[str] = None
    ativa: bool = True


class CategoryOut(BaseModel):
    """Representação pública de uma categoria."""

    id: str
    nome: str
    descricao: Optional[str]
    ativa: bool

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)
