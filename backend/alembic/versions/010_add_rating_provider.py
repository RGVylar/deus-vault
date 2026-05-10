"""add rating and provider to contents

Revision ID: 010
Revises: 009
Create Date: 2026-05-10

"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contents",
        sa.Column("rating", sa.Float(), nullable=True),
    )
    op.add_column(
        "contents",
        sa.Column("provider", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contents", "provider")
    op.drop_column("contents", "rating")
