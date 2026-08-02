"""store Dongguk crawler metadata on articles

Revision ID: c20260716dgm
Revises: b1413d2b74d1
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c20260716dgm"
down_revision: Union[str, Sequence[str], None] = "b1413d2b74d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS section VARCHAR(50)")
    op.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS pool VARCHAR(80)")
    op.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS category VARCHAR(80)")
    op.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS trusted_source BOOLEAN")
    op.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS priority_boost DOUBLE PRECISION")
    op.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS board VARCHAR(80)")
    op.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS board_name VARCHAR(255)")


def downgrade() -> None:
    op.drop_column("articles", "board_name")
    op.drop_column("articles", "board")
    op.drop_column("articles", "priority_boost")
    op.drop_column("articles", "trusted_source")
    op.drop_column("articles", "category")
    op.drop_column("articles", "pool")
    op.drop_column("articles", "section")
