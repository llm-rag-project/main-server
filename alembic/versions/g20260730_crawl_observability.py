"""add crawl observability records

Revision ID: g20260730obs
Revises: f20260730ins
Create Date: 2026-07-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "g20260730obs"
down_revision: Union[str, Sequence[str], None] = "f20260730ins"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crawl_run_sources",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("crawl_run_id", sa.BigInteger(), nullable=False),
        sa.Column("keyword_id", sa.BigInteger(), nullable=False),
        sa.Column("source_name", sa.String(length=60), nullable=False),
        sa.Column("trigger_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("discovered_count", sa.Integer(), nullable=False),
        sa.Column("processed_count", sa.Integer(), nullable=False),
        sa.Column("stored_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("rejected_date_count", sa.Integer(), nullable=False),
        sa.Column("rejected_relevance_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("is_reconstructed", sa.Boolean(), nullable=False),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["crawl_run_id"], ["crawl_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["keyword_id"], ["keywords.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "crawl_run_id",
            "keyword_id",
            "source_name",
            name="uq_crawl_run_source_run_keyword_source",
        ),
    )
    op.create_index(
        "ix_crawl_run_sources_keyword_created",
        "crawl_run_sources",
        ["keyword_id", "created_at"],
    )
    op.create_index(
        "ix_crawl_run_sources_status_created",
        "crawl_run_sources",
        ["status", "created_at"],
    )

    op.create_table(
        "crawl_run_articles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("crawl_run_id", sa.BigInteger(), nullable=False),
        sa.Column("keyword_id", sa.BigInteger(), nullable=False),
        sa.Column("article_id", sa.BigInteger(), nullable=True),
        sa.Column("source_name", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("reason_code", sa.String(length=60), nullable=True),
        sa.Column("candidate_url", sa.Text(), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_reconstructed", sa.Boolean(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["crawl_run_id"], ["crawl_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["keyword_id"], ["keywords.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crawl_run_articles_run_status", "crawl_run_articles", ["crawl_run_id", "status"])
    op.create_index("ix_crawl_run_articles_keyword_created", "crawl_run_articles", ["keyword_id", "created_at"])
    op.create_index("ix_crawl_run_articles_canonical_url", "crawl_run_articles", ["canonical_url"])


def downgrade() -> None:
    op.drop_index("ix_crawl_run_articles_canonical_url", table_name="crawl_run_articles")
    op.drop_index("ix_crawl_run_articles_keyword_created", table_name="crawl_run_articles")
    op.drop_index("ix_crawl_run_articles_run_status", table_name="crawl_run_articles")
    op.drop_table("crawl_run_articles")
    op.drop_index("ix_crawl_run_sources_status_created", table_name="crawl_run_sources")
    op.drop_index("ix_crawl_run_sources_keyword_created", table_name="crawl_run_sources")
    op.drop_table("crawl_run_sources")
