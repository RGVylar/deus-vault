"""add distraction_logs table

Revision ID: 020
Revises: 019
Create Date: 2026-07-08
"""
import sqlalchemy as sa
from alembic import op

revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'distraction_logs',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('date', sa.Date, nullable=False),
        sa.Column('platform', sa.String(30), nullable=False),
        sa.Column('seconds', sa.Integer, nullable=False, server_default='0'),
        sa.Column('items_count', sa.Integer, nullable=False, server_default='0'),
        sa.UniqueConstraint('user_id', 'date', 'platform', name='uq_distraction_user_date_platform'),
    )
    op.create_index('ix_distraction_user_date', 'distraction_logs', ['user_id', 'date'])


def downgrade() -> None:
    op.drop_index('ix_distraction_user_date', 'distraction_logs')
    op.drop_table('distraction_logs')
