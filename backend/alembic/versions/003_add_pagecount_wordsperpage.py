"""add page_count and words_per_page to contents

Revision ID: 003
Revises: 002
Create Date: 2026-04-15

"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contents", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column("contents", sa.Column("words_per_page", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("contents", "words_per_page")
    op.drop_column("contents", "page_count")
