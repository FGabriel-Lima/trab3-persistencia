"""
Script de população de dados — insere dados realistas no MongoDB.

Uso:
    # Com Docker Compose em execução:
    docker compose exec api python scripts/seed_data.py

    # Ou localmente (com .env configurado):
    python scripts/seed_data.py

Garante no mínimo 100 registros por entidade principal, respeitando todas
as relações de chave estrangeira. Usa Faker com locale pt_BR para dados
coerentes e realistas (nomes, endereços, textos em português).
"""

import asyncio
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Garante que o módulo `app` seja encontrado independente de onde o script é chamado
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from faker import Faker
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.config import settings
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.complaint_status import ComplaintStatus, STATUSES_PADRAO
from app.models.documento import Documento
from app.models.location import Location
from app.models.service_response import ServiceResponse
from app.models.user import User

fake = Faker("pt_BR")
Faker.seed(42)
random.seed(42)

# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

CATEGORIAS = [
    ("Buraco na via", "Problemas com pavimentação e buracos em vias públicas"),
    ("Iluminação pública", "Postes apagados ou com defeito"),
    ("Coleta de lixo", "Falha na coleta regular de resíduos domiciliares"),
    ("Poda de árvore", "Árvores com galhos que obstruem calçadas ou fiação"),
    ("Esgoto a céu aberto", "Vazamentos e extravasamento de esgoto"),
    ("Calçada danificada", "Calçadas quebradas, irregulares ou com obstáculos"),
    ("Descarte irregular de lixo", "Descarte de entulho e lixo em locais proibidos"),
    ("Sinal de trânsito", "Semáforos com defeito ou apagados"),
    ("Vandalismo em bem público", "Depredação de praças, monumentos e mobiliário urbano"),
    ("Alagamento", "Pontos de alagamento recorrentes em períodos de chuva"),
    ("Animal abandonado", "Animais domésticos encontrados em situação de abandono"),
    ("Ruído excessivo", "Perturbação do sossego por estabelecimentos ou obras"),
]

BAIRROS = [
    "Centro", "Vila Madalena", "Pinheiros", "Moema", "Itaim Bibi",
    "Lapa", "Santana", "Penha", "Tucuruvi", "Santo André",
    "Jardim Paulista", "Consolação", "República", "Bela Vista",
    "Liberdade", "Ipiranga", "Tatuapé", "Saúde", "Campo Belo", "Morumbi",
]

ORGAOS = [
    "SUBPREFEITURA CENTRO", "SABESP", "ENEL DISTRIBUIÇÃO",
    "PREFEITURA REGIONAL LAPA", "AMLURB", "CET SP",
    "SVMA", "SMT", "SUBPREFEITURA MOOCA",
]


# =============================================================================
# Funções auxiliares
# =============================================================================

def data_aleatoria(dias_atras: int = 365) -> datetime:
    """Gera uma data aleatória dentro dos últimos N dias."""
    delta = timedelta(days=random.randint(0, dias_atras))
    return datetime.now(timezone.utc) - delta


def cpf_fake() -> str:
    """Gera uma string de 11 dígitos que simula um CPF (não válido oficialmente)."""
    return "".join([str(random.randint(0, 9)) for _ in range(11)])


def localizacao_fake(bairro: str) -> Location:
    """Cria um documento de localização coerente com o bairro fornecido."""
    return Location(
        bairro=bairro,
        rua=fake.street_name(),
        numero=str(random.randint(1, 9999)),
        complemento=random.choice([None, "Próximo ao semáforo", "Em frente ao número par", None]),
        cep="".join([str(random.randint(0, 9)) for _ in range(8)]),
        cidade="São Paulo",
        estado="SP",
        latitude=round(random.uniform(-23.7, -23.4), 6),
        longitude=round(random.uniform(-46.8, -46.4), 6),
    )


# =============================================================================
# Inserção por entidade
# =============================================================================

async def criar_categorias() -> list[Category]:
    """Insere as categorias pré-definidas de denúncia."""
    print("  → Criando categorias...")
    categorias = []
    for nome, descricao in CATEGORIAS:
        existente = await Category.find_one({"nome": nome})
        if existente:
            categorias.append(existente)
            continue
        cat = Category(nome=nome, descricao=descricao, ativa=True)
        await cat.insert()
        categorias.append(cat)
    print(f"     {len(categorias)} categorias prontas.")
    return categorias


async def criar_statuses() -> list[ComplaintStatus]:
    """Insere os status padrão do fluxo de atendimento."""
    print("  → Criando status...")
    statuses = []
    for ordem, nome in enumerate(STATUSES_PADRAO):

        existente = await ComplaintStatus.find_one({"nome": nome})
        if existente:
            statuses.append(existente)
            continue
        st = ComplaintStatus(nome=nome, descricao=f"Denúncia no estado: {nome}", ordem=ordem)
        await st.insert()
        statuses.append(st)
    print(f"     {len(statuses)} status prontos.")
    return statuses


async def criar_usuarios(quantidade: int = 120) -> list[User]:
    """Insere usuários com dados fictícios mas coerentes."""
    print(f"  → Criando {quantidade} usuários...")
    usuarios = []
    emails_usados: set[str] = set()
    cpfs_usados: set[str] = set()

    while len(usuarios) < quantidade:
        email = fake.email()
        cpf = cpf_fake()
        if email in emails_usados or cpf in cpfs_usados:
            continue
        emails_usados.add(email)
        cpfs_usados.add(cpf)

        criado_em = data_aleatoria(730)
        usuario = User(
            nome=fake.name(),
            email=email,
            cpf=cpf,
            telefone=fake.phone_number(),
            ativo=random.choices([True, False], weights=[90, 10])[0],
            created_at=criado_em,
            updated_at=criado_em,
        )
        await usuario.insert()
        usuarios.append(usuario)

    print(f"     {len(usuarios)} usuários criados.")
    return usuarios


async def criar_denuncias(
    usuarios: list[User],
    categorias: list[Category],
    statuses: list[ComplaintStatus],
    quantidade: int = 200,
) -> list[Complaint]:
    """Insere denúncias com relações coerentes a usuários, categorias e status."""
    print(f"  → Criando {quantidade} denúncias...")
    denuncias = []

    titulos_base = [
        "Buraco perigoso", "Poste apagado há semanas", "Lixo acumulado na esquina",
        "Árvore bloqueando a calçada", "Esgoto transbordando", "Calçada esburacada",
        "Entulho descartado irregularmente", "Semáforo sem funcionar",
        "Pichação em monumento histórico", "Alagamento recorrente",
        "Cachorro abandonado", "Barulho insuportável de bar",
    ]

    for i in range(quantidade):
        bairro = random.choice(BAIRROS)
        categoria = random.choice(categorias)
        status = random.choices(statuses, weights=[30, 25, 20, 15, 10][:len(statuses)])[0]
        usuario = random.choice(usuarios)
        criado_em = data_aleatoria(365)

        titulo_base = random.choice(titulos_base)
        titulo = f"{titulo_base} — {bairro} ({i + 1})"
        descricao = (
            f"{fake.paragraph(nb_sentences=3)} "
            f"O problema está localizado na {fake.street_name()}, {bairro}. "
            f"{fake.paragraph(nb_sentences=2)}"
        )

        denuncia = Complaint(
            titulo=titulo,
            descricao=descricao,
            usuario=usuario,  # type: ignore[arg-type]
            categoria=categoria,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            localizacao=localizacao_fake(bairro),
            prioridade=random.randint(1, 5),
            created_at=criado_em,
            updated_at=criado_em,
        )
        await denuncia.insert()
        denuncias.append(denuncia)

    print(f"     {len(denuncias)} denúncias criadas.")
    return denuncias


async def criar_atendimentos(
    denuncias: list[Complaint],
    quantidade: int = 100,
) -> list[ServiceResponse]:
    """
    Cria atendimentos vinculando múltiplas denúncias a cada um.

    Demonstra o relacionamento Many-to-Many: cada atendimento pode
    referenciar entre 1 e 4 denúncias, e cada denúncia pode ter
    vários atendimentos.
    """
    print(f"  → Criando {quantidade} atendimentos (Many-to-Many)...")
    atendimentos = []

    for i in range(quantidade):
        # Cada atendimento abrange entre 1 e 4 denúncias (M:M)
        qtd_denuncias = random.randint(1, 4)
        denuncias_vinculadas = random.sample(denuncias, min(qtd_denuncias, len(denuncias)))

        criado_em = data_aleatoria(300)
        previsao = criado_em + timedelta(days=random.randint(3, 30)) if random.random() > 0.3 else None
        concluido = random.random() > 0.6

        atendimento = ServiceResponse(
            descricao=(
                f"Ordem de serviço #{1000 + i}: {fake.paragraph(nb_sentences=2)} "
                f"Equipe técnica designada para verificação e correção no local."
            ),
            responsavel=fake.name(),
            orgao=random.choice(ORGAOS),
            previsao_conclusao=previsao,
            concluido=concluido,
            created_at=criado_em,
            updated_at=criado_em,
            denuncias=denuncias_vinculadas,  # type: ignore[arg-type]
        )
        await atendimento.insert()
        atendimentos.append(atendimento)

        # Atualiza o lado inverso da relação M:M nas denúncias
        for denuncia in denuncias_vinculadas:
            denuncia.atendimentos.append(atendimento)  # type: ignore[arg-type]
            await denuncia.save()

    print(f"     {len(atendimentos)} atendimentos criados.")
    return atendimentos


async def criar_documentos(
    denuncias: list[Complaint],
    quantidade: int = 150,
) -> list[Documento]:
    """
    Cria registros de documentos (metadados) vinculados a denúncias.

    Não faz upload real ao MinIO — gera object_keys fictícios para o seed.
    Em produção, o upload ocorre via endpoint POST /denuncias/{id}/documents.
    """
    print(f"  → Criando {quantidade} documentos (metadados)...")
    documentos = []

    tipos_arquivo = [
        ("image/jpeg", "jpg"), ("image/png", "png"),
        ("image/webp", "webp"), ("video/mp4", "mp4"),
        ("video/quicktime", "mov"),
    ]

    denuncias_com_docs = random.sample(denuncias, min(quantidade, len(denuncias)))
    # Algumas denúncias recebem mais de um documento
    todas_denuncias_para_docs = denuncias_com_docs + random.sample(
        denuncias, min(quantidade - len(denuncias_com_docs), len(denuncias))
    )

    for i, denuncia in enumerate(todas_denuncias_para_docs[:quantidade]):
        content_type, extension = random.choice(tipos_arquivo)
        object_key = f"denuncias/{denuncia.id}/seed_{uuid.uuid4()}.{extension}"
        criado_em = data_aleatoria(300)

        doc = Documento(
            original_filename=f"foto_{i + 1:04d}.{extension}",
            content_type=content_type,
            extension=extension,
            size_bytes=random.randint(50_000, 8_000_000),  # 50 KB a 8 MB
            bucket_name="denuncias-bucket",
            object_key=object_key,
            denuncia=denuncia,  # type: ignore[arg-type]
            descricao=random.choice([
                "Foto do local do problema",
                "Imagem evidenciando o buraco",
                "Vídeo registrando o alagamento",
                "Foto tirada às 8h da manhã",
                None,
            ]),
            created_at=criado_em,
            updated_at=criado_em,
        )
        await doc.insert()
        documentos.append(doc)

    print(f"     {len(documentos)} documentos criados.")
    return documentos


# =============================================================================
# Orquestração principal
# =============================================================================

async def main() -> None:
    """Conecta ao banco e executa o seed completo na ordem correta."""
    print("\n========================================")
    print("  SEED — Sistema de Denúncias Urbanas")
    print("========================================\n")

    client = AsyncIOMotorClient(settings.mongodb_uri)
    await init_beanie(
        database=client[settings.mongodb_database],
        document_models=[User, Category, ComplaintStatus, Complaint, ServiceResponse, Documento],
    )

    print("  → Limpando dados existentes...")
    for model in [Documento, ServiceResponse, Complaint, ComplaintStatus, Category, User]:
        await model.get_motor_collection().drop()
    print("     Coleções limpas.\n")

    categorias = await criar_categorias()
    statuses = await criar_statuses()
    usuarios = await criar_usuarios(120)
    denuncias = await criar_denuncias(usuarios, categorias, statuses, 200)
    await criar_atendimentos(denuncias, 110)
    await criar_documentos(denuncias, 160)

    print("\n========================================")
    print("  Seed concluído com sucesso!")
    print(f"  Banco: {settings.mongodb_database}")
    print("========================================\n")


if __name__ == "__main__":
    asyncio.run(main())
