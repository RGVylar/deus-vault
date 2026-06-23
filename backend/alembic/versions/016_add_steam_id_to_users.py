"""add steam_id to users

Revision ID: 016
Revises: 015
Create Date: 2026-06-23
"""
import sqlalchemy as sa
from alembic import op

revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('steam_id', sa.String(25), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'steam_id')
