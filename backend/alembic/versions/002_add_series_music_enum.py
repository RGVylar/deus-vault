"""add series and music to contenttype enum

Revision ID: 002
Revises: 001
Create Date: 2026-04-15

"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new enum values safely if they don't exist
    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'contenttype' AND e.enumlabel = 'series'
        ) THEN
            ALTER TYPE contenttype ADD VALUE 'series';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'contenttype' AND e.enumlabel = 'music'
        ) THEN
            ALTER TYPE contenttype ADD VALUE 'music';
        END IF;
    END$$;
    """
    )


def downgrade() -> None:
    # Downgrading enum values is non-trivial; leave as no-op.
    pass
