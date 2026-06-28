"""Endpoints de Usuários — CRUD completo com paginação."""

from datetime import datetime, timezone

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query
from fastapi_pagination import Page
from fastapi_pagination.ext.beanie import paginate

from app.models.user import User, UserIn, UserOut

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


@router.post("/", response_model=UserOut, status_code=201)
async def criar_usuario(payload: UserIn) -> UserOut:
    """
    Cadastra um novo usuário no sistema.

    Retorna 400 se o e-mail ou CPF já estiver em uso.
    """
    existente = await User.find_one(
        {"$or": [{"email": payload.email}, {"cpf": payload.cpf}]}
    )
    if existente:
        raise HTTPException(status_code=400, detail="E-mail ou CPF já cadastrado.")

    usuario = User(**payload.model_dump())
    await usuario.insert()
    return _to_out(usuario)


@router.get("/", response_model=Page[UserOut])
async def listar_usuarios(
    ativo: bool | None = Query(default=None, description="Filtrar por status ativo/inativo"),
    busca: str | None = Query(default=None, description="Busca parcial por nome (case-insensitive)"),
) -> Page[UserOut]:
    """
    Lista usuários com paginação.

    Suporta filtro por status e busca textual parcial no nome.
    """
    filtro: dict = {}
    if ativo is not None:
        filtro["ativo"] = ativo
    if busca:
        filtro["nome"] = {"$regex": busca, "$options": "i"}

    query = User.find(filtro).sort("-created_at")
    return await paginate(query, transformer=lambda items: [_to_out(u) for u in items])  # type: ignore[arg-type]


@router.get("/{usuario_id}", response_model=UserOut)
async def obter_usuario(usuario_id: PydanticObjectId) -> UserOut:
    """Retorna um usuário pelo seu ID."""
    usuario = await User.get(usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return _to_out(usuario)


@router.put("/{usuario_id}", response_model=UserOut)
async def atualizar_usuario(usuario_id: PydanticObjectId, payload: UserIn) -> UserOut:
    """Atualiza todos os dados de um usuário existente."""
    usuario = await User.get(usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # Verifica conflito de email/cpf com outro usuário
    conflito = await User.find_one(
        {
            "$and": [
                {"_id": {"$ne": usuario_id}},
                {"$or": [{"email": payload.email}, {"cpf": payload.cpf}]},
            ]
        }
    )
    if conflito:
        raise HTTPException(status_code=400, detail="E-mail ou CPF já em uso por outro usuário.")

    await usuario.set(
        {
            **payload.model_dump(),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    return _to_out(usuario)


@router.delete("/{usuario_id}", status_code=204)
async def deletar_usuario(usuario_id: PydanticObjectId) -> None:
    """Remove um usuário. Bloqueado se houver denúncias vinculadas."""
    from app.models.complaint import Complaint

    usuario = await User.get(usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    em_uso = await Complaint.find_one({"usuario.$id": usuario_id})
    if em_uso:
        raise HTTPException(
            status_code=409,
            detail="Usuário possui denúncias vinculadas e não pode ser removido.",
        )
    await usuario.delete()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_out(usuario: User) -> UserOut:
    """Converte um documento User para o schema de saída."""
    return UserOut(
        id=str(usuario.id),
        nome=usuario.nome,
        email=usuario.email,
        telefone=usuario.telefone,
        ativo=usuario.ativo,
        created_at=usuario.created_at,
    )
