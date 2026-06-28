"""Inicialização da conexão com o MongoDB via Beanie."""

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.complaint_status import ComplaintStatus
from app.models.documento import Documento
from app.models.service_response import ServiceResponse
from app.models.user import User


Documento.model_rebuild(_types_namespace={"Complaint": Complaint})


async def init_database() -> None:
    """Conecta ao MongoDB e inicializa o Beanie com todos os document models."""
    client = AsyncIOMotorClient(settings.mongodb_uri)
    await init_beanie(
        database=client[settings.mongodb_database],
        document_models=[
            User,
            Category,
            ComplaintStatus,
            Complaint,
            ServiceResponse,
            Documento,
        ],
    )
