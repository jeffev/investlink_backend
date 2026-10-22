"""
Postgres de verdade, descartável, para os testes de integração.

Por que existe, depois de 429 testes unitários:
    Os unitários rodam em SQLite e com mock. Isso cobre a lógica e esconde
    exatamente as três coisas que já quebraram este projeto em produção —
    a ordenação com NULLS LAST, que o SQLite resolve ao contrário; o
    `ON CONFLICT`, que precisa de uma restrição de unicidade existindo de fato;
    e a cadeia de migrações do Alembic, que nenhum teste jamais aplicou.

O contêiner sobe uma vez por sessão e morre no fim. Nada toca o banco de
desenvolvimento.
"""

import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

POSTGRES_IMAGE = "postgres:13"


def _docker_disponivel():
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:
        return False


requer_docker = pytest.mark.skipif(
    not _docker_disponivel(),
    reason="Docker não está no ar; os testes de integração precisam dele",
)


@pytest.fixture(scope="session")
def postgres_url():
    """URL de um Postgres 13 novo — a mesma versão do docker-compose."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(POSTGRES_IMAGE) as container:
        yield container.get_connection_url()


@pytest.fixture(scope="session")
def app(postgres_url):
    """
    A aplicação real, com as rotas registradas e o schema criado **pelas
    migrações** — não por `create_all`.

    É o que transforma a cadeia do Alembic em algo verificado: se uma revisão
    referencia uma tabela que não existe ainda, ou duas revisões disputam o
    mesmo `down_revision`, a sessão inteira falha aqui.
    """
    os.environ["DATABASE_URL"] = postgres_url

    from config import create_app
    from flask_migrate import upgrade
    from utils import setup_routes

    application = create_app()
    setup_routes(application)

    with application.app_context():
        upgrade()

    return application


@pytest.fixture
def db_session(app):
    """
    Sessão limpa por teste.

    Trunca no fim em vez de no começo: um teste que falha deixa o banco no
    estado em que falhou, e o seguinte não herda nada.
    """
    from config import db

    with app.app_context():
        yield db.session

        db.session.rollback()

        # Só as tabelas que existem de fato: o metadata do backend também
        # declara as quatro que pertencem ao pipeline de dados, e essas o
        # `flask db upgrade` não cria.
        from sqlalchemy import inspect

        existentes = set(inspect(db.engine).get_table_names()) - {"alembic_version"}
        alvos = [
            tabela.name
            for tabela in reversed(db.metadata.sorted_tables)
            if tabela.name in existentes
        ]
        if alvos:
            nomes = ",".join(f'"{nome}"' for nome in alvos)
            db.session.execute(db.text(f"TRUNCATE {nomes} RESTART IDENTITY CASCADE"))
            db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()
