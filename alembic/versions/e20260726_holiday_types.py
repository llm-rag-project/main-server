"""add school and personal holiday types

Revision ID: e20260726typ
Revises: d20260726hol
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e20260726typ"
down_revision: Union[str, Sequence[str], None] = "d20260726hol"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "school_holidays",
        sa.Column(
            "holiday_type",
            sa.String(length=20),
            server_default=sa.text("'school'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("school_holidays", "holiday_type")
