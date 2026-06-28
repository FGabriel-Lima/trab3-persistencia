"""Endpoints de Status de Denúncia — CRUD com paginação."""

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException
from fastapi_pagination import Page
from fastapi_pagination.ext.beanie import paginate

from app.models.complaint_status import ComplaintStatus, ComplaintStatusIn, ComplaintStatusOut

router = APIRouter(prefix="/status", tags=["Status"])


@router.post("/", response_model=ComplaintStatusOut, status_code=201)
async def criar_status(payload: ComplaintStatusIn) -> ComplaintStatusOut:
    """Cria um novo status no fluxo de denúncias."""
    existente = await ComplaintStatus.find_one({"nome": payload.nome})
    if existente:
        raise HTTPException(status_code=400, detail="Status com este nome já existe.")

    status = ComplaintStatus(**payload.model_dump())
    await status.insert()
    return _to_out(status)


@router.get("/", response_model=Page[ComplaintStatusOut])
async def listar_status() -> Page[ComplaintStatusOut]:
    """Lista todos os status disponíveis, ordenados pelo campo `ordem`."""
    query = ComplaintStatus.find().sort("ordem")
    return await paginate(query)  # type: ignore[arg-type]


@router.get("/{status_id}", response_model=ComplaintStatusOut)
async def obter_status(status_id: PydanticObjectId) -> ComplaintStatusOut:
    """Retorna um status pelo ID."""
    status = await ComplaintStatus.get(status_id)
    if not status:
        raise HTTPException(status_code=404, detail="Status não encontrado.")
    return _to_out(status)


@router.put("/{status_id}", response_model=ComplaintStatusOut)
async def atualizar_status(status_id: PydanticObjectId, payload: ComplaintStatusIn) -> ComplaintStatusOut:
    """Atualiza um status existente."""
    status = await ComplaintStatus.get(status_id)
    if not status:
        raise HTTPException(status_code=404, detail="Status não encontrado.")

    conflito = await ComplaintStatus.find_one(
        {"nome": payload.nome, "_id": {"$ne": status_id}}
    )
    if conflito:
        raise HTTPException(status_code=400, detail="Já existe outro status com este nome.")

    await status.set(payload.model_dump())
    return _to_out(status)


@router.delete("/{status_id}", status_code=204)
async def deletar_status(status_id: PydanticObjectId) -> None:
    """Remove um status. Bloqueado se houver denúncias vinculadas."""
    from app.models.complaint import Complaint

    status = await ComplaintStatus.get(status_id)
    if not status:
        raise HTTPException(status_code=404, detail="Status não encontrado.")

    em_uso = await Complaint.find_one({"status.$id": status_id})
    if em_uso:
        raise HTTPException(
            status_code=409,
            detail="Status em uso por uma ou mais denúncias e não pode ser removido.",
        )
    await status.delete()


def _to_out(status: ComplaintStatus) -> ComplaintStatusOut:
    return ComplaintStatusOut(
        id=str(status.id),
        nome=status.nome,
        descricao=status.descricao,
        ordem=status.ordem,
    )
