"""add episode_count and seasons to contents

Revision ID: 004
Revises: 003
Create Date: 2026-04-16

"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contents", sa.Column("episode_count", sa.Integer(), nullable=True))
    op.add_column("contents", sa.Column("seasons", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("contents", "seasons")
    op.drop_column("contents", "episode_count")
