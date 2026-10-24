"""add the cycle pillar to the FII score

Mesma pergunta que o lado das ações passou a responder: o score dizia "é bom?"
contra os vizinhos de segmento e não dizia "é hora?". Cota colada na máxima de
12 meses e cota 30% abaixo recebiam a mesma nota.

A queda só pontua quando o patrimônio por cota está de pé — sem esse filtro o
pilar premiaria o fundo que está encolhendo, que foi exatamente o que pôs os
quatro fundos de crédito em aflição no topo da vitrine.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-10-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("fii_scores", sa.Column("score_ciclo", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("fii_scores", "score_ciclo")
