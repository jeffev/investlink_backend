"""add FII indicators and the FII score

Quatro indicadores que o Fundamentus já publicava e que ninguém estava lendo:
FFO yield, quantidade de imóveis, cap rate e vacância média. São o que
distingue um fundo de tijolo com prédio vazio de um com prédio alugado, e
estavam sendo jogados fora a cada atualização.

fii_scores guarda o score de quatro pilares com seus motivos e alertas, uma
linha por ticker e perfil — tabela separada de stock_scores porque os pilares
de um FII não são os de uma ação.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("fiis", sa.Column("ffo_yield", sa.Float(), nullable=True))
    op.add_column("fiis", sa.Column("qtd_imoveis", sa.Integer(), nullable=True))
    op.add_column("fiis", sa.Column("cap_rate", sa.Float(), nullable=True))
    op.add_column("fiis", sa.Column("vacancia_media", sa.Float(), nullable=True))

    op.create_table(
        "fii_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("profile", sa.String(length=20), nullable=False),
        sa.Column("run_date", sa.DateTime(), nullable=False),
        sa.Column("score_total", sa.Float(), nullable=True),
        sa.Column("score_valuation", sa.Float(), nullable=True),
        sa.Column("score_renda", sa.Float(), nullable=True),
        sa.Column("score_liquidez", sa.Float(), nullable=True),
        sa.Column("score_estrutura", sa.Float(), nullable=True),
        sa.Column("eligible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("exclusion_reasons", sa.Text(), nullable=True),
        sa.Column("reasons", sa.Text(), nullable=True),
        sa.Column("red_flags", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["ticker"], ["fiis.ticker"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fii_scores_ticker", "fii_scores", ["ticker"])
    # A vitrine lê sempre por perfil e ordena por score; sem este índice a
    # consulta varre a tabela inteira a cada abertura da tela.
    op.create_index("ix_fii_scores_profile_total", "fii_scores", ["profile", "score_total"])


def downgrade():
    op.drop_index("ix_fii_scores_profile_total", table_name="fii_scores")
    op.drop_index("ix_fii_scores_ticker", table_name="fii_scores")
    op.drop_table("fii_scores")

    op.drop_column("fiis", "vacancia_media")
    op.drop_column("fiis", "cap_rate")
    op.drop_column("fiis", "qtd_imoveis")
    op.drop_column("fiis", "ffo_yield")
