"""add fundamentals provenance to stocks

Records where each stock's accounting figures came from and how recent they
are. Without it the screener silently mixes audited trailing-twelve-month
numbers with scraped last-closed-year ones, and nothing on screen says which
is which.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-09 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "stocks",
        sa.Column("fundamentals_source", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "stocks",
        sa.Column("fundamentals_date", sa.Date(), nullable=True),
    )


def downgrade():
    op.drop_column("stocks", "fundamentals_date")
    op.drop_column("stocks", "fundamentals_source")
