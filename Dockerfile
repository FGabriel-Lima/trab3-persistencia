FROM python:3.11-slim

# Instala o uv para gerenciamento de dependências
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copia os arquivos de dependências primeiro (aproveita cache de camadas)
COPY pyproject.toml .

# Instala todas as dependências diretamente via uv no Python do sistema
RUN uv pip install --system --no-cache \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.30.0" \
        "beanie>=1.26.0,<2.0.0" \
        "motor>=3.5.0" \
        "pydantic[email]>=2.8.0" \
        "email-validator>=2.1.0" \
        "pydantic-settings>=2.4.0" \
        "minio>=7.2.0" \
        "python-multipart>=0.0.9" \
        "fastapi-pagination>=0.12.26" \
        "faker>=26.0.0" \
        "python-dotenv>=1.0.1" \
        "httpx>=0.27.0"

# Copia o código-fonte
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY .env.example .env

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
