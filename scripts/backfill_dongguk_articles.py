import argparse
import asyncio
import json
import logging
import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import exists, func, literal, select

from app.core.transnews_client import TransNewsClient
from app.db.session import AsyncSessionLocal, engine
from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.dongguk_article_trash import DonggukArticleTrash
from app.models.keyword import Keyword
from app.services.auto_ai_service import AutoAiService
from app.services.crawl_run_service import CrawlRunService


KST = ZoneInfo("Asia/Seoul")
logger = logging.getLogger("dongguk-backfill")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill Dongguk articles one calendar day at a time."
    )
    parser.add_argument("--keyword-id", type=int, required=True)
    parser.add_argument("--from-date", type=date.fromisoformat, required=True)
    parser.add_argument("--to-date", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Collect and link articles without summary/importance processing.",
    )
    parser.add_argument("--ai-batch-size", type=int, default=100)
    parser.add_argument("--delay-seconds", type=float, default=0.2)
    parser.add_argument("--max-retries", type=int, default=3)
    return parser.parse_args()


def iter_dates(start_date: date, end_date: date):
    cursor = start_date
    while cursor <= end_date:
        yield cursor
        cursor += timedelta(days=1)


async def crawl_day(*, keyword: Keyword, target_date: date) -> tuple[dict, list[int]]:
    start_at = datetime.combine(target_date, time.min, tzinfo=KST)
    end_at = datetime.combine(target_date, time.max, tzinfo=KST)

    async with AsyncSessionLocal() as db:
        service = CrawlRunService(db=db, transnews_client=TransNewsClient())
        result = await service.create_crawl_run(
            user_id=keyword.user_id,
            keyword_ids=[keyword.id],
            force=True,
            custom_start_at=start_at,
            custom_end_at=end_at,
            trigger_type="backfill",
            capture_social_metrics=False,
            discovery_only=True,
            enrich_for_relevance=True,
        )
        article_ids_result = await db.execute(
            select(ArticleMatch.article_id)
            .where(ArticleMatch.crawl_run_id == result["crawl_run_id"])
            .distinct()
        )
        article_ids = [row[0] for row in article_ids_result.all()]
        return result, article_ids


async def run_ai(*, user_id: int, article_ids: list[int], batch_size: int) -> dict:
    totals = {
        "summary_count": 0,
        "importance_count": 0,
        "already_scored_count": 0,
        "remaining_count": 0,
    }
    unique_ids = list(dict.fromkeys(article_ids))
    for offset in range(0, len(unique_ids), batch_size):
        batch = unique_ids[offset : offset + batch_size]
        async with AsyncSessionLocal() as db:
            result = await AutoAiService(db).run_for_articles(
                user_id=user_id,
                article_ids=batch,
            )
        for key in totals:
            totals[key] += int(result.get(key) or 0)
        logger.info(
            "AI progress %s/%s articles: %s",
            min(offset + len(batch), len(unique_ids)),
            len(unique_ids),
            json.dumps(result, ensure_ascii=False),
        )
    return totals


async def article_counts_by_date(
    *, keyword_id: int, start_date: date, end_date: date
) -> dict[str, int]:
    published_date = func.date(func.timezone("Asia/Seoul", Article.published_at))
    is_trashed = exists(
        select(literal(1))
        .select_from(DonggukArticleTrash)
        .where(
            DonggukArticleTrash.keyword_id == keyword_id,
            DonggukArticleTrash.article_id == Article.id,
        )
    )
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(published_date, func.count(func.distinct(Article.id)))
            .join(ArticleMatch, ArticleMatch.article_id == Article.id)
            .where(
                ArticleMatch.keyword_id == keyword_id,
                published_date.between(start_date, end_date),
                ~is_trashed,
            )
            .group_by(published_date)
            .order_by(published_date)
        )
    return {
        row[0].isoformat(): int(row[1])
        for row in result.all()
        if row[0] is not None
    }


async def article_ids_in_date_range(
    *, keyword_id: int, start_date: date, end_date: date
) -> list[int]:
    published_date = func.date(func.timezone("Asia/Seoul", Article.published_at))
    is_trashed = exists(
        select(literal(1))
        .select_from(DonggukArticleTrash)
        .where(
            DonggukArticleTrash.keyword_id == keyword_id,
            DonggukArticleTrash.article_id == Article.id,
        )
    )
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Article.id)
            .join(ArticleMatch, ArticleMatch.article_id == Article.id)
            .where(
                ArticleMatch.keyword_id == keyword_id,
                published_date.between(start_date, end_date),
                ~is_trashed,
            )
            .distinct()
            .order_by(Article.id)
        )
    return [row[0] for row in result.all()]


async def main() -> None:
    args = parse_args()
    if args.from_date > args.to_date:
        raise SystemExit("--from-date must be before or equal to --to-date")
    if args.ai_batch_size < 1 or args.ai_batch_size > 100:
        raise SystemExit("--ai-batch-size must be between 1 and 100")

    async with AsyncSessionLocal() as db:
        keyword = await db.get(Keyword, args.keyword_id)
        if keyword is None:
            raise SystemExit(f"keyword_id={args.keyword_id} does not exist")
        keyword_snapshot = Keyword(
            id=keyword.id,
            user_id=keyword.user_id,
            keyword_text=keyword.keyword_text,
            is_active=keyword.is_active,
            crawl_interval_minutes=keyword.crawl_interval_minutes,
            crawl_limit=keyword.crawl_limit,
            email_send_time=keyword.email_send_time,
        )

    all_new_article_ids: list[int] = []
    before_counts = await article_counts_by_date(
        keyword_id=keyword_snapshot.id,
        start_date=args.from_date,
        end_date=args.to_date,
    )
    completed_days = 0
    failed_days: list[dict[str, str]] = []
    accepted_total = 0
    upload_total = 0

    for target_date in iter_dates(args.from_date, args.to_date):
        last_error = None
        for attempt in range(1, args.max_retries + 1):
            try:
                result, new_article_ids = await crawl_day(
                    keyword=keyword_snapshot,
                    target_date=target_date,
                )
                completed_days += 1
                accepted_total += int(result.get("crawl_count") or 0)
                upload_total += int(result.get("upload_target_count") or 0)
                all_new_article_ids.extend(new_article_ids)
                logger.info(
                    "date=%s run_id=%s accepted=%s new_matches=%s uploaded=%s failed_uploads=%s",
                    target_date.isoformat(),
                    result.get("crawl_run_id"),
                    result.get("crawl_count"),
                    len(new_article_ids),
                    result.get("dify_uploaded_count"),
                    result.get("dify_failed_count"),
                )
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                logger.exception(
                    "Backfill attempt %s/%s failed for %s",
                    attempt,
                    args.max_retries,
                    target_date.isoformat(),
                )
                if attempt < args.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 10))

        if last_error is not None:
            failed_days.append(
                {"date": target_date.isoformat(), "error": str(last_error)}
            )

        if args.delay_seconds > 0:
            await asyncio.sleep(args.delay_seconds)

    ai_result = None
    analysis_article_ids: list[int] = []
    if not args.skip_ai:
        analysis_article_ids = await article_ids_in_date_range(
            keyword_id=keyword_snapshot.id,
            start_date=args.from_date,
            end_date=args.to_date,
        )
        ai_result = await run_ai(
            user_id=keyword_snapshot.user_id,
            article_ids=analysis_article_ids,
            batch_size=args.ai_batch_size,
        )

    after_counts = await article_counts_by_date(
        keyword_id=keyword_snapshot.id,
        start_date=args.from_date,
        end_date=args.to_date,
    )
    daily_changes = {
        target_date.isoformat(): {
            "before": before_counts.get(target_date.isoformat(), 0),
            "after": after_counts.get(target_date.isoformat(), 0),
            "added": (
                after_counts.get(target_date.isoformat(), 0)
                - before_counts.get(target_date.isoformat(), 0)
            ),
        }
        for target_date in iter_dates(args.from_date, args.to_date)
    }
    result = {
        "keyword_id": keyword_snapshot.id,
        "keyword": keyword_snapshot.keyword_text,
        "from_date": args.from_date.isoformat(),
        "to_date": args.to_date.isoformat(),
        "completed_days": completed_days,
        "failed_days": failed_days,
        "accepted_total": accepted_total,
        "upload_target_total": upload_total,
        "new_article_count": len(set(all_new_article_ids)),
        "analysis_article_count": len(analysis_article_ids),
        "before_total": sum(before_counts.values()),
        "after_total": sum(after_counts.values()),
        "added_total": sum(after_counts.values()) - sum(before_counts.values()),
        "daily_changes": daily_changes,
        "ai_result": ai_result,
    }
    print(json.dumps(result, ensure_ascii=False))
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, os.getenv("BACKFILL_LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(main())
