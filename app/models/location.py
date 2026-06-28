"""Modelo de Localização — documento embutido na Denúncia."""

from typing import Optional

from pydantic import BaseModel, Field


class Location(BaseModel):
    """
    Localização geográfica onde o problema foi identificado.

    Documento embutido (embedded) na Denúncia — não possui coleção própria.
    """

    bairro: str = Field(..., min_length=2, max_length=100)
    rua: str = Field(..., min_length=2, max_length=150)
    numero: Optional[str] = None
    complemento: Optional[str] = None
    cep: Optional[str] = Field(default=None, pattern=r"^\d{8}$")
    cidade: str = "São Paulo"
    estado: str = Field(default="SP", max_length=2)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
