"""add started_at to contents

Revision ID: 015
Revises: 014
Create Date: 2026-06-23
"""
import sqlalchemy as sa
from alembic import op

revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('contents', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('contents', 'started_at')
