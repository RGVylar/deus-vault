"""add channel_thumbnail to contents

Revision ID: 008
Revises: 007
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contents", sa.Column("channel_thumbnail", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("contents", "channel_thumbnail")
