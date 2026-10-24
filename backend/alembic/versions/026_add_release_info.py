"""add release_date and coming_soon to contents

Revision ID: 026
Revises: 025
Create Date: 2026-10-24
"""
import sqlalchemy as sa
from alembic import op

revision = '026'
down_revision = '025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('contents', sa.Column('release_date', sa.Date(), nullable=True))
    # sa.false() y no un "0" literal: Postgres no acepta 0 como boolean y SQLite
    # no tiene booleanos; cada dialecto lo traduce a lo suyo.
    op.add_column('contents', sa.Column('coming_soon', sa.Boolean(), nullable=False, server_default=sa.false()))
    # Las películas ya guardaban su estreno en next_episode_date: se copia para
    # que salgan marcadas sin tener que refrescarlas una a una.
    op.execute(
        "UPDATE contents SET release_date = DATE(next_episode_date) "
        "WHERE content_type = 'movie' AND next_episode_date IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column('contents', 'coming_soon')
    op.drop_column('contents', 'release_date')
