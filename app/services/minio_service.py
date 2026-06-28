"""Serviço de integração com o MinIO para upload/download de arquivos."""

import io
import uuid
from datetime import timedelta
from typing import BinaryIO, Generator

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class MinioService:
    """Encapsula todas as operações de armazenamento de objetos com o MinIO."""

    def __init__(self) -> None:
        self._client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket = settings.minio_bucket
        self._ensure_bucket_exists()

    # ------------------------------------------------------------------
    # Inicialização
    # ------------------------------------------------------------------

    @property
    def bucket_name(self) -> str:
        """Nome do bucket padrão configurado."""
        return self._bucket

    def _ensure_bucket_exists(self) -> None:
        """Cria o bucket padrão caso ainda não exista."""
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload_file(
        self,
        file_data: BinaryIO,
        content_type: str,
        extension: str,
        size_bytes: int,
        prefix: str = "uploads",
    ) -> str:
        """
        Faz upload de um arquivo para o MinIO e retorna a object_key gerada.

        Args:
            file_data: Stream binário do arquivo.
            content_type: MIME type do arquivo (ex: 'image/jpeg').
            extension: Extensão sem ponto (ex: 'jpg').
            size_bytes: Tamanho do arquivo em bytes.
            prefix: Diretório virtual dentro do bucket.

        Returns:
            object_key única que identifica o objeto no MinIO.
        """
        object_key = f"{prefix}/{uuid.uuid4()}.{extension}"
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=object_key,
            data=file_data,
            length=size_bytes,
            content_type=content_type,
        )
        return object_key

    # ------------------------------------------------------------------
    # Download / URL pré-assinada
    # ------------------------------------------------------------------

    def get_presigned_url(self, object_key: str, expires_minutes: int = 60) -> str:
        """
        Gera uma URL pré-assinada para acesso temporário ao arquivo.

        Args:
            object_key: Caminho do objeto no bucket.
            expires_minutes: Validade da URL em minutos.

        Returns:
            URL pré-assinada como string.
        """
        return self._client.presigned_get_object(
            bucket_name=self._bucket,
            object_name=object_key,
            expires=timedelta(minutes=expires_minutes),
        )

    def download_file(self, object_key: str) -> Generator[bytes, None, None]:
        """
        Retorna um gerador que produz o arquivo em chunks de 64 KB.

        Args:
            object_key: Caminho do objeto no bucket.

        Raises:
            S3Error: Caso o objeto não exista ou haja erro de comunicação.
        """
        response = self._client.get_object(
            bucket_name=self._bucket,
            object_name=object_key,
        )
        try:
            yield from response.stream(amt=65536)
        finally:
            response.close()
            response.release_conn()

    # ------------------------------------------------------------------
    # Deleção
    # ------------------------------------------------------------------

    def delete_file(self, object_key: str) -> None:
        """
        Remove um objeto do bucket MinIO.

        Args:
            object_key: Caminho do objeto a ser removido.
        """
        try:
            self._client.remove_object(
                bucket_name=self._bucket,
                object_name=object_key,
            )
        except S3Error as exc:
            # Loga mas não propaga — o objeto pode já ter sido deletado
            print(f"[MinIO] Aviso ao deletar {object_key}: {exc}")

    # ------------------------------------------------------------------
    # Verificação
    # ------------------------------------------------------------------

    def file_exists(self, object_key: str) -> bool:
        """Verifica se um objeto existe no bucket."""
        try:
            self._client.stat_object(self._bucket, object_key)
            return True
        except S3Error:
            return False
