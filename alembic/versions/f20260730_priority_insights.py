"""add Dongguk priority learning and insight history

Revision ID: f20260730ins
Revises: e20260726typ
Create Date: 2026-07-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f20260730ins"
down_revision: Union[str, Sequence[str], None] = "e20260726typ"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dongguk_priority_actions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("keyword_id", sa.BigInteger(), nullable=True),
        sa.Column("article_id", sa.BigInteger(), nullable=True),
        sa.Column("mail_date", sa.String(length=10), nullable=True),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("source_screen", sa.String(length=40), nullable=False),
        sa.Column("article_key", sa.String(length=500), nullable=True),
        sa.Column("article_title", sa.Text(), nullable=True),
        sa.Column("article_category", sa.String(length=100), nullable=True),
        sa.Column("article_priority", sa.String(length=30), nullable=True),
        sa.Column("before_body", sa.Text(), nullable=True),
        sa.Column("after_body", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["keyword_id"], ["keywords.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dongguk_priority_action_user_keyword_created",
        "dongguk_priority_actions",
        ["user_id", "keyword_id", "created_at"],
    )
    op.create_index(
        "ix_dongguk_priority_action_type_created",
        "dongguk_priority_actions",
        ["action_type", "created_at"],
    )

    op.create_table(
        "dongguk_priority_insights",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("keyword_id", sa.BigInteger(), nullable=False),
        sa.Column("period_key", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("cadence", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("evidence_body", sa.Text(), nullable=False),
        sa.Column("criteria_before", sa.Text(), nullable=False),
        sa.Column("criteria_after", sa.Text(), nullable=False),
        sa.Column("changes_body", sa.Text(), nullable=False),
        sa.Column("generated_by", sa.String(length=30), nullable=False),
        sa.Column("workflow_run_id", sa.String(length=255), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["keyword_id"], ["keywords.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "keyword_id",
            "period_key",
            "cadence",
            name="uq_dongguk_priority_insight_period",
        ),
    )
    op.create_index(
        "ix_dongguk_priority_insight_user_keyword_period",
        "dongguk_priority_insights",
        ["user_id", "keyword_id", "period_start"],
    )
    op.create_index(
        "ix_dongguk_priority_insight_status",
        "dongguk_priority_insights",
        ["status", "period_end"],
    )


def downgrade() -> None:
    op.drop_index("ix_dongguk_priority_insight_status", table_name="dongguk_priority_insights")
    op.drop_index("ix_dongguk_priority_insight_user_keyword_period", table_name="dongguk_priority_insights")
    op.drop_table("dongguk_priority_insights")
    op.drop_index("ix_dongguk_priority_action_type_created", table_name="dongguk_priority_actions")
    op.drop_index("ix_dongguk_priority_action_user_keyword_created", table_name="dongguk_priority_actions")
    op.drop_table("dongguk_priority_actions")
