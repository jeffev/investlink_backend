"""add a grace period before a stock counts as delisted

A coleta de ações trocou de fonte e, na primeira execução, 71 papéis que não
aparecem na lista nova foram marcados como fora do pregão de uma vez — entre
eles a **B3SA3**, que é a própria bolsa. Ausência de um dia numa fonte não é
deslistagem.

`missing_since` guarda desde quando o papel sumiu; só depois de alguns dias
seguidos fora da fonte ele é desativado. Quem reaparece tem a marca limpa.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-10-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("stocks", sa.Column("missing_since", sa.Date(), nullable=True))

    # Conserta o estrago da troca de fonte: devolve ao pregão quem foi
    # desativado hoje, sem carência nenhuma.
    op.execute(
        """
        UPDATE stocks
           SET active = true,
               delisted_at = NULL
         WHERE active = false
           AND delisted_at = CURRENT_DATE
        """
    )


def downgrade():
    op.drop_column("stocks", "missing_since")
