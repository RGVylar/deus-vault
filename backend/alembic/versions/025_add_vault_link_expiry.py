"""add expiry to vault links and duration to invites

Revision ID: 025
Revises: 024
Create Date: 2026-09-11
"""
import sqlalchemy as sa
from alembic import op

revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('vault_links', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('vault_invites', sa.Column('link_hours', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('vault_invites', 'link_hours')
    op.drop_column('vault_links', 'expires_at')
