"""add synopsis to contents

Revision ID: 021
Revises: 020
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('contents', sa.Column('synopsis', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('contents', 'synopsis')
