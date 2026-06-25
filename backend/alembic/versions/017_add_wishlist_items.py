"""add wishlist_items table

Revision ID: 017
Revises: 016
Create Date: 2026-06-25
"""
import sqlalchemy as sa
from alembic import op

revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'wishlist_items',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('url', sa.Text, nullable=True),
        sa.Column('price', sa.Float, nullable=True),
        sa.Column('image_url', sa.Text, nullable=True),
        sa.Column('store', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('purchased', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('purchased_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_wishlist_user_id', 'wishlist_items', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_wishlist_user_id', 'wishlist_items')
    op.drop_table('wishlist_items')
