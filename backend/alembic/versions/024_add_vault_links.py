"""add vault_links and vault_invites tables

Revision ID: 024
Revises: 023
Create Date: 2026-09-11
"""
import sqlalchemy as sa
from alembic import op

revision = '024'
down_revision = '023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'vault_links',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_a_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('user_b_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('user_a_id', 'user_b_id', name='uq_vault_link_pair'),
    )
    op.create_table(
        'vault_invites',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('token', sa.String(32), nullable=False, unique=True),
        sa.Column('inviter_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('vault_invites')
    op.drop_table('vault_links')
