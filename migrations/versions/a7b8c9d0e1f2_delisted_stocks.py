"""mark stocks that disappeared from the source instead of leaving them adrift

update_all_stocks only ever wrote the tickers the source returned, so a company
that stopped being listed simply stayed in the table with its last known price
forever. TRAD3 gave it away: 618 rows in stocks against 617 in the payload.

Marked, not deleted. A user may hold a delisted ticker in their portfolio or
favourites, and deleting the row would take their position history with it.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-10 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "stocks",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("stocks", sa.Column("delisted_at", sa.Date(), nullable=True))
    op.create_index("ix_stocks_active", "stocks", ["active"])


def downgrade():
    op.drop_index("ix_stocks_active", table_name="stocks")
    op.drop_column("stocks", "delisted_at")
    op.drop_column("stocks", "active")
