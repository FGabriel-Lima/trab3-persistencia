"""
Ponto de entrada da aplicação FastAPI.

Responsabilidades deste módulo:
- Criação e configuração da instância FastAPI.
- Registro dos routers de cada entidade.
- Inicialização da conexão com o banco de dados (lifespan).
- Tratamento global de exceções.
- Configuração do middleware de CORS.
- Integração do fastapi-pagination.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_pagination import add_pagination

from app.core.config import settings
from app.core.database import init_database
from app.routes import (
    categories,
    complaints,
    documents,
    service_responses,
    statuses,
    users,
)


# =============================================================================
# Lifespan — conecta ao banco na inicialização
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerencia o ciclo de vida da aplicação: conecta ao DB ao iniciar."""
    await init_database()
    yield
    # cleanup se necessário (motor fecha automaticamente)


# =============================================================================
# Criação da aplicação
# =============================================================================

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=(
        "API REST para gerenciamento de denúncias urbanas. "
        "Permite que cidadãos registrem problemas na cidade e acompanhem "
        "o atendimento pelo poder público."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ajuste para domínios específicos em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(statuses.router)
app.include_router(complaints.router)
app.include_router(service_responses.router)
app.include_router(documents.router)

# ---------------------------------------------------------------------------
# Paginação global (fastapi-pagination)
# ---------------------------------------------------------------------------
add_pagination(app)


# =============================================================================
# Tratamento global de exceções
# =============================================================================

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Captura erros de validação de valores e retorna 400."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Captura exceções não tratadas e retorna 500 sem expor detalhes internos."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Erro interno do servidor. Tente novamente mais tarde."},
    )


# =============================================================================
# Endpoints utilitários
# =============================================================================

@app.get("/", tags=["Saúde"])
async def raiz() -> dict:
    """Endpoint raiz — confirma que a API está no ar."""
    return {
        "sistema": settings.api_title,
        "versao": settings.api_version,
        "documentacao": "/docs",
    }


@app.get("/health", tags=["Saúde"])
async def health_check() -> dict:
    """Health check para uso com orquestradores (Docker, k8s)."""
    return {"status": "ok"}
