"""add manga to contenttype enum

Revision ID: 023
Revises: 022
Create Date: 2026-08-10

"""
from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite has no native enum type — values are stored as plain strings, no migration needed.
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return

    op.execute(
        """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = 'contenttype' AND e.enumlabel = 'manga'
        ) THEN
            ALTER TYPE contenttype ADD VALUE 'manga';
        END IF;
    END$$;
    """
    )


def downgrade() -> None:
    # Downgrading enum values is non-trivial; leave as no-op (same as 002).
    pass
