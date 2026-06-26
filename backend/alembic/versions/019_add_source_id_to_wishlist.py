"""add source_id to wishlist_items

Revision ID: 019
Revises: 018
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "wishlist_items",
        sa.Column("source_id", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wishlist_items", "source_id")
