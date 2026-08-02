from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_run import CrawlRun
from app.models.crawl_run_article import CrawlRunArticle
from app.models.crawl_run_source import CrawlRunSource


TERMINAL_SUCCESS_STATUSES = {"success", "empty", "reconstructed"}
TERMINAL_FAILURE_STATUSES = {"failed", "timeout", "partial", "skipped_locked"}


def reconciliation_delta(source: CrawlRunSource) -> int:
    outcomes = (
        int(source.stored_count or 0)
        + int(source.duplicate_count or 0)
        + int(source.rejected_date_count or 0)
        + int(source.rejected_relevance_count or 0)
        + int(source.failed_count or 0)
    )
    return int(source.discovered_count or 0) - outcomes


class CrawlHealthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def summary(
        self,
        *,
        user_id: int,
        keyword_id: int | None = None,
        days: int = 30,
        limit: int = 50,
    ) -> dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 180)))
        stmt = (
            select(CrawlRunSource, CrawlRun)
            .join(CrawlRun, CrawlRun.id == CrawlRunSource.crawl_run_id)
            .where(CrawlRun.user_id == user_id)
            .where(CrawlRunSource.created_at >= cutoff)
            .order_by(CrawlRunSource.created_at.desc(), CrawlRunSource.id.desc())
        )
        if keyword_id:
            stmt = stmt.where(CrawlRunSource.keyword_id == keyword_id)
        rows = (await self.db.execute(stmt)).all()

        source_counts: dict[str, Counter] = defaultdict(Counter)
        run_rows: dict[int, dict[str, Any]] = {}
        last_success_at = None
        exact_runs = 0
        reconstructed_runs: set[int] = set()

        for source, run in rows:
            if source.source_name not in {"merged_pipeline", "coordination"}:
                source_counts[source.source_name]["runs"] += 1
                source_counts[source.source_name][source.status] += 1
                source_counts[source.source_name]["discovered"] += int(source.discovered_count or 0)
                source_counts[source.source_name]["retries"] += int(source.retry_count or 0)
                if source.duration_ms:
                    source_counts[source.source_name]["duration_total_ms"] += int(source.duration_ms)
                    source_counts[source.source_name]["duration_samples"] += 1

            if source.status in TERMINAL_SUCCESS_STATUSES and not source.is_reconstructed:
                if last_success_at is None or source.created_at > last_success_at:
                    last_success_at = source.created_at

            if source.is_reconstructed:
                reconstructed_runs.add(int(run.id))

            run_item = run_rows.setdefault(
                int(run.id),
                {
                    "run_id": int(run.id),
                    "status": run.status,
                    "article_count": int(run.article_count or 0),
                    "started_at": run.started_at,
                    "finished_at": run.finished_at,
                    "window_start": source.window_start,
                    "window_end": source.window_end,
                    "trigger_type": source.trigger_type,
                    "is_reconstructed": bool(source.is_reconstructed),
                    "sources": [],
                    "has_warning": False,
                    "reconciliation_delta": None,
                },
            )
            run_item["is_reconstructed"] = run_item["is_reconstructed"] or bool(source.is_reconstructed)
            run_item["has_warning"] = run_item["has_warning"] or source.status in TERMINAL_FAILURE_STATUSES
            if source.source_name == "merged_pipeline":
                delta = reconciliation_delta(source)
                run_item["reconciliation_delta"] = delta
                if delta == 0:
                    exact_runs += 1
                else:
                    run_item["has_warning"] = True
            else:
                diagnostics = source.diagnostics or {}
                run_item["sources"].append(
                    {
                        "name": source.source_name,
                        "status": source.status,
                        "discovered_count": int(source.discovered_count or 0),
                        "stored_count": int(source.stored_count or 0),
                        "duplicate_count": int(source.duplicate_count or 0),
                        "rejected_count": int(source.rejected_date_count or 0)
                        + int(source.rejected_relevance_count or 0),
                        "failed_count": int(source.failed_count or 0),
                        "retry_count": int(source.retry_count or 0),
                        "duration_ms": source.duration_ms,
                        "error_message": source.error_message,
                        "section": diagnostics.get("section"),
                        "empty_reason": diagnostics.get("empty_reason"),
                        "is_reconstructed": bool(source.is_reconstructed),
                    }
                )

        sources = []
        for source_name, counts in sorted(source_counts.items()):
            run_count = int(counts["runs"])
            success_count = sum(int(counts[name]) for name in TERMINAL_SUCCESS_STATUSES)
            sources.append(
                {
                    "name": source_name,
                    "run_count": run_count,
                    "success_count": success_count,
                    "failure_count": sum(int(counts[name]) for name in TERMINAL_FAILURE_STATUSES),
                    "success_rate": round(success_count * 100 / run_count, 1) if run_count else 0,
                    "discovered_count": int(counts["discovered"]),
                    "retry_count": int(counts["retries"]),
                    "average_duration_ms": round(
                        counts["duration_total_ms"] / counts["duration_samples"]
                    )
                    if counts["duration_samples"]
                    else None,
                }
            )

        recent_runs = list(run_rows.values())[: max(1, min(limit, 100))]
        warning_runs = sum(1 for item in run_rows.values() if item["has_warning"])
        exact_candidates = [
            item for item in run_rows.values()
            if not item["is_reconstructed"] and item["reconciliation_delta"] is not None
        ]
        return {
            "period_days": days,
            "last_success_at": last_success_at,
            "run_count": len(run_rows),
            "warning_run_count": warning_runs,
            "reconstructed_run_count": len(reconstructed_runs),
            "reconciled_run_count": sum(
                1 for item in exact_candidates if item["reconciliation_delta"] == 0
            ),
            "reconciliation_target_count": len(exact_candidates),
            "sources": sources,
            "recent_runs": recent_runs,
        }

    async def run_detail(self, *, user_id: int, run_id: int) -> dict[str, Any] | None:
        run = await self.db.scalar(
            select(CrawlRun).where(CrawlRun.id == run_id, CrawlRun.user_id == user_id)
        )
        if run is None:
            return None
        sources = list(
            (
                await self.db.execute(
                    select(CrawlRunSource)
                    .where(CrawlRunSource.crawl_run_id == run_id)
                    .order_by(CrawlRunSource.source_name)
                )
            ).scalars()
        )
        articles = list(
            (
                await self.db.execute(
                    select(CrawlRunArticle)
                    .where(CrawlRunArticle.crawl_run_id == run_id)
                    .order_by(CrawlRunArticle.id)
                )
            ).scalars()
        )
        reason_counts = Counter(
            article.reason_code or article.status for article in articles
        )
        return {
            "run_id": int(run.id),
            "status": run.status,
            "article_count": int(run.article_count or 0),
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "sources": [
                {
                    "name": source.source_name,
                    "status": source.status,
                    "trigger_type": source.trigger_type,
                    "window_start": source.window_start,
                    "window_end": source.window_end,
                    "discovered_count": int(source.discovered_count or 0),
                    "processed_count": int(source.processed_count or 0),
                    "stored_count": int(source.stored_count or 0),
                    "duplicate_count": int(source.duplicate_count or 0),
                    "rejected_date_count": int(source.rejected_date_count or 0),
                    "rejected_relevance_count": int(source.rejected_relevance_count or 0),
                    "failed_count": int(source.failed_count or 0),
                    "retry_count": int(source.retry_count or 0),
                    "duration_ms": source.duration_ms,
                    "error_message": source.error_message,
                    "section": (source.diagnostics or {}).get("section"),
                    "empty_reason": (source.diagnostics or {}).get("empty_reason"),
                    "is_reconstructed": bool(source.is_reconstructed),
                    "reconciliation_delta": reconciliation_delta(source)
                    if source.source_name == "merged_pipeline"
                    else None,
                }
                for source in sources
            ],
            "article_status_counts": dict(Counter(article.status for article in articles)),
            "reason_counts": dict(reason_counts),
            "articles": [
                {
                    "id": int(article.id),
                    "article_id": int(article.article_id) if article.article_id else None,
                    "source_name": article.source_name,
                    "status": article.status,
                    "reason_code": article.reason_code,
                    "title": article.title,
                    "url": article.candidate_url,
                    "published_at": article.published_at,
                    "is_reconstructed": bool(article.is_reconstructed),
                }
                for article in articles[:500]
            ],
        }
