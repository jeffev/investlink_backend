"""store the FII cycle signal alongside the stock one

O card precisa falar a mesma língua nos dois ativos: "caiu X% do topo de 12
meses" vale para a ação e para a cota. Os três campos já eram calculados em
memória a cada score; agora ficam gravados, como já acontecia do lado das
ações.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-10-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("fiis", sa.Column("queda_12m", sa.Float(), nullable=True))
    op.add_column("fiis", sa.Column("cycle_state", sa.String(length=30), nullable=True))
    op.add_column(
        "fiis", sa.Column("cycle_message", sa.String(length=255), nullable=True)
    )


def downgrade():
    op.drop_column("fiis", "cycle_message")
    op.drop_column("fiis", "cycle_state")
    op.drop_column("fiis", "queda_12m")
