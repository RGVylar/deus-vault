"""add gifted to wishlist_items

Revision ID: 018
Revises: 017
Create Date: 2026-06-25
"""
import sqlalchemy as sa
from alembic import op

revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('wishlist_items', sa.Column('gifted', sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('wishlist_items', 'gifted')
