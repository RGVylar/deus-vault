"""add performance indexes to contents

Revision ID: 014
Revises: 013
Create Date: 2026-06-13
"""
from alembic import op

revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('ix_contents_user_pending', 'contents', ['user_id', 'consumed', 'abandoned'])
    op.create_index('ix_contents_user_consumed_at', 'contents', ['user_id', 'consumed', 'consumed_at'])
    op.create_index('ix_contents_user_abandoned', 'contents', ['user_id', 'abandoned'])
    op.create_index('ix_contents_user_type', 'contents', ['user_id', 'content_type'])
    op.create_index('ix_contents_created_at', 'contents', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_contents_created_at', table_name='contents')
    op.drop_index('ix_contents_user_type', table_name='contents')
    op.drop_index('ix_contents_user_abandoned', table_name='contents')
    op.drop_index('ix_contents_user_consumed_at', table_name='contents')
    op.drop_index('ix_contents_user_pending', table_name='contents')
