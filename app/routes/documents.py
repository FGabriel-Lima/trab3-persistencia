"""
Endpoints de Documentos — upload, download e gestão de metadados.

Fluxo de upload:
  1. Recebe o arquivo via multipart/form-data.
  2. Faz upload para o MinIO (armazenamento de objetos).
  3. Persiste apenas os metadados no MongoDB (coleção `documentos`).

Fluxo de download:
  - Gera URL pré-assinada no MinIO para acesso temporário.
"""

import io
import os
from datetime import datetime, timezone
from typing import List

from beanie import PydanticObjectId
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.beanie import paginate

from app.core.dependencies import MinioServiceDep
from app.models.complaint import Complaint
from app.models.documento import Documento, DocumentoOut, DocumentoUpdate

router = APIRouter(tags=["Documentos"])


# =============================================================================
# Documentos de uma denúncia específica
# =============================================================================

@router.post("/denuncias/{denuncia_id}/documents", response_model=DocumentoOut, status_code=201)
async def upload_documento(
    denuncia_id: PydanticObjectId,
    minio: MinioServiceDep,
    arquivo: UploadFile = File(..., description="Arquivo (imagem ou vídeo) a ser enviado"),
    descricao: str = Form(default=""),
) -> DocumentoOut:
    """
    Faz upload de um arquivo para o MinIO e registra os metadados no MongoDB.

    O arquivo é enviado via multipart/form-data. Apenas metadados (nome,
    tipo, tamanho, chave no MinIO) são armazenados no banco.
    """
    denuncia = await Complaint.get(denuncia_id)
    if not denuncia:
        raise HTTPException(status_code=404, detail="Denúncia não encontrada.")

    if not arquivo.filename:
        raise HTTPException(status_code=400, detail="Nome do arquivo não fornecido.")

    conteudo = await arquivo.read()
    tamanho = len(conteudo)
    extension = os.path.splitext(arquivo.filename)[-1].lstrip(".").lower() or "bin"
    content_type = arquivo.content_type or "application/octet-stream"

    try:
        object_key = minio.upload_file(
            file_data=io.BytesIO(conteudo),
            content_type=content_type,
            extension=extension,
            size_bytes=tamanho,
            prefix=f"denuncias/{denuncia_id}",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha no upload para o MinIO: {exc}")

    documento = Documento(
        original_filename=arquivo.filename,
        content_type=content_type,
        extension=extension,
        size_bytes=tamanho,
        bucket_name=minio.bucket_name,
        object_key=object_key,
        denuncia=denuncia,  # type: ignore[arg-type]
        descricao=descricao or None,
    )
    await documento.insert()
    return _to_out(documento)


@router.get("/denuncias/{denuncia_id}/documents", response_model=Page[DocumentoOut])
async def listar_documentos_da_denuncia(denuncia_id: PydanticObjectId) -> Page[DocumentoOut]:
    """
    Lista os documentos (metadados) vinculados a uma denúncia específica.

    Retorna paginado — nunca a coleção inteira.
    """
    denuncia = await Complaint.get(denuncia_id)
    if not denuncia:
        raise HTTPException(status_code=404, detail="Denúncia não encontrada.")

    query = Documento.find({"denuncia.$id": denuncia_id}).sort("-created_at")
    return await paginate(query)  # type: ignore[arg-type]


# =============================================================================
# Operações diretas em documentos
# =============================================================================

@router.get("/documents/{document_id}", response_model=DocumentoOut)
async def obter_documento(document_id: PydanticObjectId) -> DocumentoOut:
    """Retorna os metadados de um documento pelo ID."""
    documento = await Documento.get(document_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    return _to_out(documento)


@router.get("/documents/{document_id}/download")
async def download_documento(
    document_id: PydanticObjectId,
    minio: MinioServiceDep,
) -> StreamingResponse:
    """
    Baixa o arquivo diretamente do MinIO em chunks, sem carregar tudo na memória.

    Retorna StreamingResponse com o Content-Type original do arquivo.
    """
    documento = await Documento.get(document_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    try:
        stream = minio.download_file(documento.object_key)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao baixar arquivo do MinIO: {exc}")

    return StreamingResponse(
        content=stream,
        media_type=documento.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{documento.original_filename}"'
        },
    )


@router.put("/documents/{document_id}", response_model=DocumentoOut)
async def atualizar_documento(
    document_id: PydanticObjectId,
    payload: DocumentoUpdate,
) -> DocumentoOut:
    """Atualiza os metadados editáveis de um documento (descrição, nome original)."""
    documento = await Documento.get(document_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    atualizacoes = {"updated_at": datetime.now(timezone.utc)}
    if payload.descricao is not None:
        atualizacoes["descricao"] = payload.descricao  # type: ignore[assignment]
    if payload.original_filename is not None:
        atualizacoes["original_filename"] = payload.original_filename  # type: ignore[assignment]

    await documento.set(atualizacoes)
    return _to_out(documento)


@router.delete("/documents/{document_id}", status_code=204)
async def deletar_documento(
    document_id: PydanticObjectId,
    minio: MinioServiceDep,
) -> None:
    """
    Remove um documento: apaga o arquivo do MinIO e os metadados do MongoDB.

    Ordem: MinIO primeiro (reversível) → MongoDB depois (irreversível).
    """
    documento = await Documento.get(document_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    minio.delete_file(documento.object_key)
    await documento.delete()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _to_out(documento: Documento) -> DocumentoOut:
    return DocumentoOut(
        id=str(documento.id),
        original_filename=documento.original_filename,
        content_type=documento.content_type,
        extension=documento.extension,
        size_bytes=documento.size_bytes,
        created_at=documento.created_at,
        descricao=documento.descricao,
        object_key=documento.object_key,
    )
