"""add trailer_url and genres to contents

Revision ID: 011
Revises: 010
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('contents', sa.Column('trailer_url', sa.Text(), nullable=True))
    op.add_column('contents', sa.Column('genres', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('contents', 'trailer_url')
    op.drop_column('contents', 'genres')
