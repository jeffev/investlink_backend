"""add the fund name to the FII monthly history

O Fundamentus, que é a fonte primária de FII, não publica o nome do fundo — a
coleta preenchia `companyname` com o próprio ticker e a vitrine mostrava
"HGLG11" embaixo de "HGLG11". O Informe Mensal da CVM publica
`Nome_Fundo_Classe`, que o cliente já lia e descartava.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "fii_indicators_history", sa.Column("fund_name", sa.String(length=255))
    )


def downgrade():
    op.drop_column("fii_indicators_history", "fund_name")
