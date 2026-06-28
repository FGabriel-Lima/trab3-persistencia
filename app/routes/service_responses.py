"""Endpoints de Atendimentos — CRUD com suporte Many-to-Many e paginação."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query
from fastapi_pagination import Page
from fastapi_pagination.ext.beanie import paginate

from app.models.complaint import Complaint
from app.models.service_response import (
    ServiceResponse,
    ServiceResponseIn,
    ServiceResponseOut,
    ServiceResponseUpdate,
)

router = APIRouter(prefix="/atendimentos", tags=["Atendimentos"])


@router.post("/", response_model=ServiceResponseOut, status_code=201)
async def criar_atendimento(payload: ServiceResponseIn) -> ServiceResponseOut:
    """
    Registra um novo atendimento vinculando-o a uma ou mais denúncias.

    Implementa a relação Many-to-Many: persiste os links em ambos os lados.
    """
    denuncias: List[Complaint] = []
    for did in payload.denuncia_ids:
        d = await Complaint.get(PydanticObjectId(did))
        if not d:
            raise HTTPException(status_code=404, detail=f"Denúncia {did} não encontrada.")
        denuncias.append(d)

    atendimento = ServiceResponse(
        descricao=payload.descricao,
        responsavel=payload.responsavel,
        orgao=payload.orgao,
        previsao_conclusao=payload.previsao_conclusao,
        denuncias=denuncias,  # type: ignore[arg-type]
    )
    await atendimento.insert()

    # Adiciona o atendimento na lista de cada denúncia (lado inverso M:M)
    for denuncia in denuncias:
        denuncia.atendimentos.append(atendimento)  # type: ignore[arg-type]
        await denuncia.save()

    return _to_out(atendimento)


@router.get("/", response_model=Page[ServiceResponseOut])
async def listar_atendimentos(
    concluido: Optional[bool] = Query(default=None),
    denuncia_id: Optional[str] = Query(default=None, description="Filtrar por denúncia"),
) -> Page[ServiceResponseOut]:
    """Lista atendimentos com paginação, filtro por status e por denúncia."""
    filtro: Dict[str, Any] = {}
    if concluido is not None:
        filtro["concluido"] = concluido
    if denuncia_id:
        filtro["denuncias.$id"] = PydanticObjectId(denuncia_id)

    query = ServiceResponse.find(filtro).sort("-created_at")
    return await paginate(query)  # type: ignore[arg-type]


@router.get("/{atendimento_id}", response_model=ServiceResponseOut)
async def obter_atendimento(atendimento_id: PydanticObjectId) -> ServiceResponseOut:
    """Retorna um atendimento pelo ID."""
    atendimento = await ServiceResponse.get(atendimento_id)
    if not atendimento:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado.")
    return _to_out(atendimento)


@router.put("/{atendimento_id}", response_model=ServiceResponseOut)
async def atualizar_atendimento(
    atendimento_id: PydanticObjectId, payload: ServiceResponseUpdate
) -> ServiceResponseOut:
    """Atualiza parcialmente um atendimento."""
    atendimento = await ServiceResponse.get(atendimento_id)
    if not atendimento:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado.")

    atualizacoes: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}

    if payload.descricao is not None:
        atualizacoes["descricao"] = payload.descricao
    if payload.responsavel is not None:
        atualizacoes["responsavel"] = payload.responsavel
    if payload.orgao is not None:
        atualizacoes["orgao"] = payload.orgao
    if payload.previsao_conclusao is not None:
        atualizacoes["previsao_conclusao"] = payload.previsao_conclusao
    if payload.concluido is not None:
        atualizacoes["concluido"] = payload.concluido

    if payload.denuncia_ids is not None:
        denuncias: List[Complaint] = []
        for did in payload.denuncia_ids:
            d = await Complaint.get(PydanticObjectId(did))
            if not d:
                raise HTTPException(status_code=404, detail=f"Denúncia {did} não encontrada.")
            denuncias.append(d)
        atualizacoes["denuncias"] = denuncias

    await atendimento.set(atualizacoes)
    return _to_out(atendimento)


@router.delete("/{atendimento_id}", status_code=204)
async def deletar_atendimento(atendimento_id: PydanticObjectId) -> None:
    """Remove um atendimento do sistema."""
    atendimento = await ServiceResponse.get(atendimento_id)
    if not atendimento:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado.")
    await atendimento.delete()


def _to_out(atendimento: ServiceResponse) -> ServiceResponseOut:
    return ServiceResponseOut(
        id=str(atendimento.id),
        descricao=atendimento.descricao,
        responsavel=atendimento.responsavel,
        orgao=atendimento.orgao,
        concluido=atendimento.concluido,
        previsao_conclusao=atendimento.previsao_conclusao,
        created_at=atendimento.created_at,
        updated_at=atendimento.updated_at,
    )
