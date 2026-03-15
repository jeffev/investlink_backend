"""add indexes for performance

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-15 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_user_name", "users", ["user_name"], unique=True)
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"])
    op.create_index("ix_favorite_fiis_user_id", "favorites_fii", ["user_id"])


def downgrade():
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_user_name", table_name="users")
    op.drop_index("ix_favorites_user_id", table_name="favorites")
    op.drop_index("ix_favorite_fiis_user_id", table_name="favorites_fii")
