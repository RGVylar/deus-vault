"""add imdb_id to contents

Revision ID: 013
Revises: 012
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('contents', sa.Column('imdb_id', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('contents', 'imdb_id')
