"""add the unique constraint the price history was always assumed to have

The table is created by this migration chain, but written by the data science
pipeline, whose model declares UNIQUE (ticker, date) and whose insert relies on
ON CONFLICT against it. The constraint was never in the original CREATE TABLE,
so every price insert failed with "there is no unique or exclusion constraint
matching the ON CONFLICT specification" — which is why the table was still
empty and "queda do topo" was always null.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-09 00:00:00.000000

"""

from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    # Any duplicate would block the constraint. Keeping the lowest id is
    # arbitrary but safe: the rows are identical weekly quotes.
    op.execute(
        """
        DELETE FROM stock_prices_history a
        USING stock_prices_history b
        WHERE a.id > b.id AND a.ticker = b.ticker AND a.date = b.date
        """
    )
    op.create_unique_constraint(
        "uq_price_ticker_date", "stock_prices_history", ["ticker", "date"]
    )


def downgrade():
    op.drop_constraint(
        "uq_price_ticker_date", "stock_prices_history", type_="unique"
    )
