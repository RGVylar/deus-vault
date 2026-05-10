"""add times_consumed and next_episode_date to contents

Revision ID: 009
Revises: 008
Create Date: 2026-05-10

"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contents",
        sa.Column("times_consumed", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "contents",
        sa.Column("next_episode_date", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contents", "next_episode_date")
    op.drop_column("contents", "times_consumed")
