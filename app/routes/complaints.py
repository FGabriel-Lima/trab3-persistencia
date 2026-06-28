"""
Endpoints de Denúncias — entidade central do sistema.

Inclui:
- CRUD completo
- Consultas complexas (filtros, texto, datas, agregações, múltiplas coleções)
- Listagem sempre paginada via fastapi-pagination
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query
from fastapi_pagination import Page
from fastapi_pagination.ext.beanie import paginate

from app.core.dependencies import MinioServiceDep
from app.models.category import Category
from app.models.complaint import Complaint, ComplaintDetailOut, ComplaintIn, ComplaintOut, ComplaintUpdate
from app.models.complaint_status import ComplaintStatus
from app.models.user import User

router = APIRouter(prefix="/denuncias", tags=["Denúncias"])


# =============================================================================
# CRUD básico
# =============================================================================

@router.post("/", response_model=ComplaintOut, status_code=201)
async def criar_denuncia(payload: ComplaintIn) -> ComplaintOut:
    """
    Registra uma nova denúncia urbana.

    Valida a existência de Usuário, Categoria e Status antes de persistir.
    """
    usuario = await User.get(payload.usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    categoria = await Category.get(payload.categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")

    status = await ComplaintStatus.get(payload.status_id)
    if not status:
        raise HTTPException(status_code=404, detail="Status não encontrado.")

    denuncia = Complaint(
        titulo=payload.titulo,
        descricao=payload.descricao,
        usuario=usuario,  # type: ignore[arg-type]
        categoria=categoria,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        localizacao=payload.localizacao,
        prioridade=payload.prioridade,
    )
    await denuncia.insert()
    return _to_out(denuncia)


@router.get("/", response_model=Page[ComplaintOut])
async def listar_denuncias(
    usuario_id: Optional[PydanticObjectId] = Query(default=None, description="Filtrar por usuário"),
    categoria_id: Optional[PydanticObjectId] = Query(default=None, description="Filtrar por categoria"),
    status_id: Optional[PydanticObjectId] = Query(default=None, description="Filtrar por status"),
    bairro: Optional[str] = Query(default=None, description="Filtrar por bairro (parcial, case-insensitive)"),
    prioridade: Optional[int] = Query(default=None, ge=1, le=5),
    ordenar_por: str = Query(default="-created_at", description="Campo de ordenação. Use '-' para desc."),
) -> Page[ComplaintOut]:
    """
    Lista denúncias com paginação e filtros.

    Suporta filtros por relacionamentos (usuário, categoria, status),
    por bairro (texto parcial) e por prioridade.
    """
    filtro: Dict[str, Any] = {}

    if usuario_id:
        filtro["usuario.$id"] = usuario_id
    if categoria_id:
        filtro["categoria.$id"] = categoria_id
    if status_id:
        filtro["status.$id"] = status_id
    if bairro:
        filtro["localizacao.bairro"] = {"$regex": bairro, "$options": "i"}
    if prioridade:
        filtro["prioridade"] = prioridade

    query = Complaint.find(filtro).sort(ordenar_por)
    return await paginate(query)  # type: ignore[arg-type]


@router.get("/{denuncia_id}", response_model=ComplaintDetailOut)
async def obter_denuncia(denuncia_id: PydanticObjectId) -> ComplaintDetailOut:
    """Retorna uma denúncia pelo ID, com usuário, categoria e status resolvidos."""
    denuncia = await Complaint.get(denuncia_id, fetch_links=True)
    if not denuncia:
        raise HTTPException(status_code=404, detail="Denúncia não encontrada.")
    return _to_detail_out(denuncia)


@router.put("/{denuncia_id}", response_model=ComplaintOut)
async def atualizar_denuncia(denuncia_id: PydanticObjectId, payload: ComplaintUpdate) -> ComplaintOut:
    """Atualiza parcialmente uma denúncia (campos opcionais no payload)."""
    denuncia = await Complaint.get(denuncia_id)
    if not denuncia:
        raise HTTPException(status_code=404, detail="Denúncia não encontrada.")

    atualizacoes: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}

    if payload.titulo is not None:
        atualizacoes["titulo"] = payload.titulo
    if payload.descricao is not None:
        atualizacoes["descricao"] = payload.descricao
    if payload.localizacao is not None:
        atualizacoes["localizacao"] = payload.localizacao
    if payload.prioridade is not None:
        atualizacoes["prioridade"] = payload.prioridade

    if payload.categoria_id:
        categoria = await Category.get(payload.categoria_id)
        if not categoria:
            raise HTTPException(status_code=404, detail="Categoria não encontrada.")
        atualizacoes["categoria"] = categoria

    if payload.status_id:
        status = await ComplaintStatus.get(payload.status_id)
        if not status:
            raise HTTPException(status_code=404, detail="Status não encontrado.")
        atualizacoes["status"] = status

    await denuncia.set(atualizacoes)
    return _to_out(denuncia)


@router.delete("/{denuncia_id}", status_code=204)
async def deletar_denuncia(denuncia_id: PydanticObjectId, minio: MinioServiceDep) -> None:
    """Remove uma denúncia, seus arquivos físicos no MinIO e os metadados de documentos."""
    from app.models.documento import Documento

    denuncia = await Complaint.get(denuncia_id)
    if not denuncia:
        raise HTTPException(status_code=404, detail="Denúncia não encontrada.")

    # Deleta arquivos físicos do MinIO antes de remover os metadados
    documentos = await Documento.find({"denuncia.$id": denuncia_id}).to_list()
    for doc in documentos:
        minio.delete_file(doc.object_key)

    await Documento.find({"denuncia.$id": denuncia_id}).delete()
    await denuncia.delete()


# =============================================================================
# Consultas complexas — Passo 4
# =============================================================================

@router.get("/busca/texto", response_model=Page[ComplaintOut], tags=["Consultas Avançadas"])
async def buscar_por_texto(
    q: str = Query(..., min_length=2, description="Texto a buscar no título ou descrição"),
) -> Page[ComplaintOut]:
    """
    Busca full-text (case-insensitive) no título e na descrição das denúncias.

    Utiliza o índice de texto do MongoDB ($text) para eficiência.
    """
    query = Complaint.find({"$text": {"$search": q}}).sort("-created_at")
    return await paginate(query)  # type: ignore[arg-type]


@router.get("/busca/por-data", response_model=Page[ComplaintOut], tags=["Consultas Avançadas"])
async def filtrar_por_data(
    data_inicio: Optional[datetime] = Query(default=None, description="Data de início (ISO 8601)"),
    data_fim: Optional[datetime] = Query(default=None, description="Data de fim (ISO 8601)"),
) -> Page[ComplaintOut]:
    """
    Filtra denúncias por intervalo de data de criação.

    Usa operadores $gte e $lte do MongoDB.
    """
    filtro: Dict[str, Any] = {}
    data_filtro: Dict[str, datetime] = {}

    if data_inicio:
        data_filtro["$gte"] = data_inicio
    if data_fim:
        data_filtro["$lte"] = data_fim
    if data_filtro:
        filtro["created_at"] = data_filtro

    query = Complaint.find(filtro).sort("-created_at")
    return await paginate(query)  # type: ignore[arg-type]


@router.get("/agregacoes/por-bairro", tags=["Consultas Avançadas"])
async def contar_por_bairro() -> List[Dict[str, Any]]:
    """
    Retorna a quantidade de denúncias agrupadas por bairro.

    Usa aggregation pipeline do MongoDB ($group + $sort).
    """
    pipeline = [
        {"$group": {"_id": "$localizacao.bairro", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}},
        {"$project": {"bairro": "$_id", "total": 1, "_id": 0}},
    ]
    resultado = await Complaint.aggregate(pipeline).to_list()
    return resultado


@router.get("/agregacoes/por-categoria", tags=["Consultas Avançadas"])
async def contar_por_categoria() -> List[Dict[str, Any]]:
    """
    Retorna a quantidade de denúncias por categoria, com o nome da categoria.

    Usa aggregation pipeline com $lookup (join com a coleção de categorias).
    """
    pipeline = [
        {
            "$group": {
                "_id": "$categoria.$id",
                "total": {"$sum": 1},
            }
        },
        {
            "$lookup": {
                "from": "categories",
                "localField": "_id",
                "foreignField": "_id",
                "as": "categoria_info",
            }
        },
        {"$unwind": {"path": "$categoria_info", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "_id": 0,
                "categoria_id": {"$toString": "$_id"},
                "categoria": "$categoria_info.nome",
                "total": 1,
            }
        },
        {"$sort": {"total": -1}},
    ]
    return await Complaint.aggregate(pipeline).to_list()


@router.get("/agregacoes/por-status", tags=["Consultas Avançadas"])
async def contar_por_status() -> List[Dict[str, Any]]:
    """
    Retorna a quantidade de denúncias por status, com join na coleção de status.

    Demonstra consulta complexa envolvendo múltiplas coleções via $lookup.
    """
    pipeline = [
        {"$group": {"_id": "$status.$id", "total": {"$sum": 1}}},
        {
            "$lookup": {
                "from": "complaint_statuses",
                "localField": "_id",
                "foreignField": "_id",
                "as": "status_info",
            }
        },
        {"$unwind": {"path": "$status_info", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "_id": 0,
                "status_id": {"$toString": "$_id"},
                "status": "$status_info.nome",
                "total": 1,
            }
        },
        {"$sort": {"status_info.ordem": 1}},
    ]
    return await Complaint.aggregate(pipeline).to_list()


@router.get("/agregacoes/detalhado", tags=["Consultas Avançadas"])
async def relatorio_detalhado(
    ano: Optional[int] = Query(default=None, description="Filtrar por ano de criação"),
) -> List[Dict[str, Any]]:
    """
    Relatório detalhado com JOIN entre Denúncia, Usuário, Categoria e Status.

    Demonstra consulta complexa envolvendo múltiplas coleções e filtro por ano.
    """
    match_stage: Dict[str, Any] = {}
    if ano:
        match_stage["$expr"] = {"$eq": [{"$year": "$created_at"}, ano]}

    pipeline: List[Dict[str, Any]] = []
    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline += [
        {
            "$lookup": {
                "from": "users",
                "localField": "usuario.$id",
                "foreignField": "_id",
                "as": "usuario_info",
            }
        },
        {
            "$lookup": {
                "from": "categories",
                "localField": "categoria.$id",
                "foreignField": "_id",
                "as": "categoria_info",
            }
        },
        {
            "$lookup": {
                "from": "complaint_statuses",
                "localField": "status.$id",
                "foreignField": "_id",
                "as": "status_info",
            }
        },
        {"$unwind": {"path": "$usuario_info", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$categoria_info", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$status_info", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "_id": 0,
                "id": {"$toString": "$_id"},
                "titulo": 1,
                "prioridade": 1,
                "bairro": "$localizacao.bairro",
                "usuario": "$usuario_info.nome",
                "categoria": "$categoria_info.nome",
                "status": "$status_info.nome",
                "created_at": 1,
            }
        },
        {"$sort": {"created_at": -1}},
        {"$limit": 200},
    ]
    return await Complaint.aggregate(pipeline).to_list()


@router.post("/{denuncia_id}/atendimentos/{atendimento_id}", status_code=200, tags=["Atendimentos"])
async def vincular_atendimento(
    denuncia_id: PydanticObjectId,
    atendimento_id: PydanticObjectId,
) -> Dict[str, str]:
    """
    Vincula um atendimento a uma denúncia (relação Many-to-Many).

    Adiciona o atendimento à lista da denúncia e a denúncia à lista do atendimento.
    """
    from app.models.service_response import ServiceResponse

    denuncia = await Complaint.get(denuncia_id)
    if not denuncia:
        raise HTTPException(status_code=404, detail="Denúncia não encontrada.")

    atendimento = await ServiceResponse.get(atendimento_id)
    if not atendimento:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado.")

    ids_existentes = [str(link.ref.id) for link in denuncia.atendimentos]  # type: ignore[union-attr]
    if str(atendimento_id) not in ids_existentes:
        denuncia.atendimentos.append(atendimento)  # type: ignore[arg-type]
        await denuncia.save()

    return {"mensagem": "Atendimento vinculado com sucesso."}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_out(denuncia: Complaint) -> ComplaintOut:
    return ComplaintOut(
        id=str(denuncia.id),
        titulo=denuncia.titulo,
        descricao=denuncia.descricao,
        prioridade=denuncia.prioridade,
        localizacao=denuncia.localizacao,
        created_at=denuncia.created_at,
        updated_at=denuncia.updated_at,
    )


def _to_detail_out(denuncia: Complaint) -> ComplaintDetailOut:
    """Constrói a resposta detalhada resolvendo links de usuário, categoria e status."""
    usuario = denuncia.usuario if not hasattr(denuncia.usuario, "ref") else None
    categoria = denuncia.categoria if not hasattr(denuncia.categoria, "ref") else None
    status = denuncia.status if not hasattr(denuncia.status, "ref") else None

    return ComplaintDetailOut(
        id=str(denuncia.id),
        titulo=denuncia.titulo,
        descricao=denuncia.descricao,
        prioridade=denuncia.prioridade,
        localizacao=denuncia.localizacao,
        usuario_id=str(usuario.id) if usuario and hasattr(usuario, "id") else None,
        usuario_nome=getattr(usuario, "nome", None),
        categoria_id=str(categoria.id) if categoria and hasattr(categoria, "id") else None,
        categoria_nome=getattr(categoria, "nome", None),
        status_id=str(status.id) if status and hasattr(status, "id") else None,
        status_nome=getattr(status, "nome", None),
        created_at=denuncia.created_at,
        updated_at=denuncia.updated_at,
    )
