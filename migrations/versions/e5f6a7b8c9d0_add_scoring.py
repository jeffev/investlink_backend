"""add traded liquidity, profit growth and the fundamental score

Two of these columns are pure recovery: StatusInvest already returns
liquidezmediadiaria and lucros_cagr5 on every refresh and the model had nowhere
to put them, so they were discarded. Traded liquidity is the guard rail that
keeps the screener from recommending something nobody can buy or sell.

stock_scores holds the five-pillar score with its reasons and red flags, one
row per ticker per profile.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-09 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("stocks", sa.Column("liquidezmediadiaria", sa.Float(), nullable=True))
    op.add_column("stocks", sa.Column("lucros_cagr5", sa.Float(), nullable=True))

    op.create_table(
        "stock_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("profile", sa.String(length=20), nullable=False),
        sa.Column("run_date", sa.DateTime(), nullable=False),
        sa.Column("score_total", sa.Float(), nullable=True),
        sa.Column("score_valuation", sa.Float(), nullable=True),
        sa.Column("score_qualidade", sa.Float(), nullable=True),
        sa.Column("score_saude", sa.Float(), nullable=True),
        sa.Column("score_crescimento", sa.Float(), nullable=True),
        sa.Column("score_dividendos", sa.Float(), nullable=True),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("exclusion_reasons", sa.Text(), nullable=True),
        sa.Column("reasons", sa.Text(), nullable=True),
        sa.Column("red_flags", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["ticker"], ["stocks.ticker"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "profile", name="uq_stock_scores_ticker_profile"),
    )
    op.create_index("ix_stock_scores_ticker", "stock_scores", ["ticker"])
    op.create_index(
        "ix_stock_scores_profile_total", "stock_scores", ["profile", "score_total"]
    )


def downgrade():
    op.drop_index("ix_stock_scores_profile_total", table_name="stock_scores")
    op.drop_index("ix_stock_scores_ticker", table_name="stock_scores")
    op.drop_table("stock_scores")
    op.drop_column("stocks", "lucros_cagr5")
    op.drop_column("stocks", "liquidezmediadiaria")
