"""
A cadeia de migrações, aplicada num Postgres vazio.

Nenhuma migração deste projeto tinha sido executada por teste nenhum. As seis
últimas — procedência do fundamento, score, unicidade do histórico de preço,
deslistagem, score de FII e histórico mensal de FII — foram escritas e nunca
aplicadas em lugar nenhum, porque o Docker esteve desligado.

Executa com:
    PYTHONPATH=app python -m pytest tests/integration -v
"""

import pytest
from sqlalchemy import inspect

from .conftest import requer_docker

pytestmark = requer_docker

MIGRATIONS_DIR = "migrations"

# O que o `flask db upgrade` do backend cria.
TABELAS_DO_BACKEND = {
    "users",
    "stocks",
    "fiis",
    "favorites",
    "favorites_fii",
    "portfolio",
    "portfolio_fii",
    "transactions",
    "strategies",
    "user_layouts",
    "stock_scores",
    "fii_scores",
    "fii_indicators_history",
    "stock_prices_history",
    "stock_predictions",
}

# O que o backend **consulta** mas quem cria é o pipeline de dados, pelo
# `data_science_pipeline/database/migrations.py`. A divisão existe porque o
# backend espelha esses models só em parte: o `CvmFinancials` daqui tem seis
# colunas e o do pipeline tem vinte e duas, então criar a tabela a partir
# daqui produziria uma tabela na qual o pipeline não conseguiria escrever.
TABELAS_DO_PIPELINE = {
    "cvm_financials",
    "cvm_fundamentals_ltm",
    "ticker_cvm_map",
    "stock_indicators_history",
}


def _tabelas(app):
    with app.app_context():
        from config import db

        return set(inspect(db.engine).get_table_names())


def test_a_cadeia_inteira_sobe_num_banco_vazio(app):
    # O fixture já rodou `upgrade()`; chegar aqui com as tabelas é o teste.
    faltando = TABELAS_DO_BACKEND - _tabelas(app)
    assert not faltando, f"Tabelas que a migração não criou: {sorted(faltando)}"


def test_o_upgrade_do_backend_nao_cria_as_tabelas_do_pipeline(app):
    """
    Isto **não** é um detalhe de arrumação: é uma lacuna de deploy.

    O `docker-entrypoint.sh` roda `flask db upgrade` e sobe a aplicação. Num
    servidor novo, `scoring_service.get_profitable_years` e o backtest
    consultam tabelas que ninguém criou — e o `except Exception` de cada
    serviço transforma isso em lista vazia, não em erro visível. É o mesmo
    modo de falha que deixou a tela de oportunidades vazia por meses.

    O teste fixa o contrato: enquanto valer, o deploy precisa rodar a migração
    do pipeline. Se um dia o backend passar a criá-las, este teste cai e a
    decisão volta a ser consciente.
    """
    criadas = _tabelas(app) & TABELAS_DO_PIPELINE
    assert not criadas, (
        "O backend passou a criar tabelas do pipeline: "
        f"{sorted(criadas)}. Reveja a divisão de propriedade."
    )


def test_o_banco_fica_na_revisao_mais_nova(app):
    from alembic.script import ScriptDirectory

    with app.app_context():
        from config import db

        gravada = db.session.execute(
            db.text("SELECT version_num FROM alembic_version")
        ).scalar()

    # O `alembic.ini` do Flask-Migrate não traz `script_location`; ele é
    # injetado em tempo de execução.
    script = ScriptDirectory(MIGRATIONS_DIR)
    assert gravada == script.get_current_head()


def test_nao_ha_duas_cabecas_na_cadeia(app):
    # Duas revisões com o mesmo `down_revision` fazem o `upgrade` falhar com
    # "Multiple head revisions" — e só na hora do deploy.
    from alembic.script import ScriptDirectory

    assert len(ScriptDirectory(MIGRATIONS_DIR).get_heads()) == 1


def test_a_tabela_de_score_de_fii_tem_as_colunas_dos_quatro_pilares(app):
    with app.app_context():
        from config import db

        colunas = {
            coluna["name"] for coluna in inspect(db.engine).get_columns("fii_scores")
        }

    assert {
        "score_valuation",
        "score_renda",
        "score_liquidez",
        "score_estrutura",
    } <= colunas


def test_o_historico_de_fii_tem_a_restricao_que_faltou_no_de_precos(app):
    # `stock_prices_history` ficou vazia a vida inteira do projeto porque não
    # tinha índice único e todo ON CONFLICT falhava. A tabela nova nasce com a
    # restrição, e este teste existe para ela não nascer sem de novo.
    with app.app_context():
        from config import db

        restricoes = inspect(db.engine).get_unique_constraints("fii_indicators_history")

    colunas = [tuple(item["column_names"]) for item in restricoes]
    assert ("ticker", "reference_date") in colunas


def test_o_historico_de_precos_ganhou_a_mesma_restricao(app):
    with app.app_context():
        from config import db

        restricoes = inspect(db.engine).get_unique_constraints("stock_prices_history")

    colunas = [tuple(item["column_names"]) for item in restricoes]
    assert ("ticker", "date") in colunas


def test_os_indicadores_novos_de_fii_existem_na_tabela(app):
    with app.app_context():
        from config import db

        colunas = {coluna["name"] for coluna in inspect(db.engine).get_columns("fiis")}

    assert {"ffo_yield", "qtd_imoveis", "cap_rate", "vacancia_media"} <= colunas


@pytest.mark.parametrize("revisao", ["c9d0e1f2a3b4", "b8c9d0e1f2a3"])
def test_as_migracoes_novas_sabem_descer_e_subir(app, revisao):
    """
    Migração que não desce é migração que não se pode reverter num deploy
    quebrado — e o rollback do F7 conta com isso para o código, não para o
    schema, justamente porque ninguém tinha verificado este lado.
    """
    from flask_migrate import downgrade, upgrade

    with app.app_context():
        downgrade(revision=f"{revisao}-1")
        upgrade(revision="head")

    assert TABELAS_DO_BACKEND <= _tabelas(app)
