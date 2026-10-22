"""add the monthly FII history

Alimentada pelo pipeline a partir do Informe Mensal da CVM (patrimônio
líquido, cotas emitidas, valor patrimonial da cota, número de cotistas) mais a
cotação de fechamento do mês e o P/VP derivado.

É o que permite dizer "este fundo está barato para ele mesmo" em vez de apenas
"barato frente aos vizinhos de segmento" — que não distingue um fundo
descontado de um segmento inteiro fora de moda.

Sem foreign key para `fiis`: a CVM recebe informe de 1.399 fundos e o
Fundamentus lista 570. Amarrar as duas pontas descartaria o histórico de um
fundo que ainda não entrou na tabela do backend e que pode entrar amanhã.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fii_indicators_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("patrimonio_liquido", sa.Float(), nullable=True),
        sa.Column("cotas_emitidas", sa.Float(), nullable=True),
        sa.Column("valor_patrimonial_cota", sa.Float(), nullable=True),
        sa.Column("numero_cotistas", sa.Float(), nullable=True),
        sa.Column("close_price", sa.Float(), nullable=True),
        sa.Column("p_vp", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        # A restrição de unicidade é o que torna o carregamento idempotente: é
        # exatamente a que faltava em stock_prices_history e deixou aquela
        # tabela vazia durante toda a vida do projeto, porque todo ON CONFLICT
        # falhava sem índice em que se apoiar.
        sa.UniqueConstraint(
            "ticker", "reference_date", name="uq_fii_history_ticker_date"
        ),
    )
    op.create_index(
        "ix_fii_indicators_history_ticker", "fii_indicators_history", ["ticker"]
    )


def downgrade():
    op.drop_index(
        "ix_fii_indicators_history_ticker", table_name="fii_indicators_history"
    )
    op.drop_table("fii_indicators_history")
