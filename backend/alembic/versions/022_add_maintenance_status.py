"""add maintenance_status to users

Revision ID: 022
Revises: 021
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('maintenance_status', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'maintenance_status')
