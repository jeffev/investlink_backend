"""add stock_predictions table

Revision ID: a1b2c3d4e5f6
Revises: b8e9822a6a2b
Create Date: 2026-03-06 13:30:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "b8e9822a6a2b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stock_predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("run_date", sa.DateTime(), nullable=False),
        sa.Column("label", sa.String(length=20), nullable=False),
        sa.Column("prob_barata", sa.Float(), nullable=True),
        sa.Column("prob_neutra", sa.Float(), nullable=True),
        sa.Column("prob_cara", sa.Float(), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["ticker"], ["stocks.ticker"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "run_date", name="uq_prediction_ticker_rundate"),
    )


def downgrade():
    op.drop_table("stock_predictions")
