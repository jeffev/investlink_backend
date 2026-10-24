"""add the cycle signal to stocks and the cycle pillar to the score

O score respondia "é bom?" comparando a empresa com as do setor e não
respondia **"é hora?"**: a mesma ação no topo histórico e 40% abaixo do pico
recebia exatamente a mesma nota.

`queda_12m`, `cycle_state` e `cycle_message` guardam onde o papel está no
próprio ciclo; `score_ciclo` é o pilar correspondente.

A queda só pontua quando o fundamento resistiu — sem esse filtro o pilar
premiaria quem está afundando, que foi exatamente o que aconteceu na primeira
execução real do score de FII.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-10-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("stocks", sa.Column("queda_12m", sa.Float(), nullable=True))
    op.add_column("stocks", sa.Column("cycle_state", sa.String(length=30), nullable=True))
    op.add_column(
        "stocks", sa.Column("cycle_message", sa.String(length=255), nullable=True)
    )
    op.add_column("stock_scores", sa.Column("score_ciclo", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("stock_scores", "score_ciclo")
    op.drop_column("stocks", "cycle_message")
    op.drop_column("stocks", "cycle_state")
    op.drop_column("stocks", "queda_12m")
