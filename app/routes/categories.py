"""Endpoints de Categorias — CRUD completo com paginação."""

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query
from fastapi_pagination import Page
from fastapi_pagination.ext.beanie import paginate

from app.models.category import Category, CategoryIn, CategoryOut

router = APIRouter(prefix="/categorias", tags=["Categorias"])


@router.post("/", response_model=CategoryOut, status_code=201)
async def criar_categoria(payload: CategoryIn) -> CategoryOut:
    """Cria uma nova categoria de denúncia."""
    existente = await Category.find_one({"nome": payload.nome})
    if existente:
        raise HTTPException(status_code=400, detail="Categoria já existe com este nome.")

    categoria = Category(**payload.model_dump())
    await categoria.insert()
    return _to_out(categoria)


@router.get("/", response_model=Page[CategoryOut])
async def listar_categorias(
    ativa: bool | None = Query(default=None),
    busca: str | None = Query(default=None, description="Busca parcial no nome"),
) -> Page[CategoryOut]:
    """Lista categorias com paginação e filtros opcionais."""
    filtro: dict = {}
    if ativa is not None:
        filtro["ativa"] = ativa
    if busca:
        filtro["nome"] = {"$regex": busca, "$options": "i"}

    query = Category.find(filtro).sort("nome")
    return await paginate(query)  # type: ignore[arg-type]


@router.get("/{categoria_id}", response_model=CategoryOut)
async def obter_categoria(categoria_id: PydanticObjectId) -> CategoryOut:
    """Retorna uma categoria pelo ID."""
    categoria = await Category.get(categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    return _to_out(categoria)


@router.put("/{categoria_id}", response_model=CategoryOut)
async def atualizar_categoria(categoria_id: PydanticObjectId, payload: CategoryIn) -> CategoryOut:
    """Atualiza os dados de uma categoria."""
    categoria = await Category.get(categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")

    conflito = await Category.find_one(
        {"nome": payload.nome, "_id": {"$ne": categoria_id}}
    )
    if conflito:
        raise HTTPException(status_code=400, detail="Já existe outra categoria com este nome.")

    await categoria.set(payload.model_dump())
    return _to_out(categoria)


@router.delete("/{categoria_id}", status_code=204)
async def deletar_categoria(categoria_id: PydanticObjectId) -> None:
    """Remove uma categoria. Bloqueado se houver denúncias vinculadas."""
    from app.models.complaint import Complaint

    categoria = await Category.get(categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")

    em_uso = await Complaint.find_one({"categoria.$id": categoria_id})
    if em_uso:
        raise HTTPException(
            status_code=409,
            detail="Categoria em uso por uma ou mais denúncias e não pode ser removida.",
        )
    await categoria.delete()


def _to_out(categoria: Category) -> CategoryOut:
    return CategoryOut(
        id=str(categoria.id),
        nome=categoria.nome,
        descricao=categoria.descricao,
        ativa=categoria.ativa,
    )
