import argparse
import asyncio
import json
import logging
from datetime import date, datetime
from pathlib import Path

from app.api.v1.reports import _dongguk_articles_for_keyword_date
from app.core.transnews_client import TransNewsClient
from app.db.session import AsyncSessionLocal, engine
from app.models.keyword import Keyword
from app.services.auto_ai_service import AutoAiService
from app.services.crawl_run_service import CrawlRunService
from app.services.holiday_service import HolidayService, article_collection_window


logger = logging.getLogger("hongbo-comparison-backfill")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill the mail dates used in the Hongbo comparison.")
    parser.add_argument("--original-json", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keyword-id", type=int, default=86)
    parser.add_argument("--include-existing", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--run-ai", action="store_true")
    parser.add_argument("--ai-batch-size", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=1)
    return parser.parse_args()


def save_progress(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


async def crawl_mail_date(*, keyword: Keyword, mail_date: str) -> dict:
    target_date = date.fromisoformat(mail_date)
    async with AsyncSessionLocal() as db:
        work_window = await HolidayService(db).work_window(keyword.user_id, target_date)
        window_start, window_end = article_collection_window(
            work_window["start_date"],
            work_window["end_date"],
            keyword.email_send_time,
        )
        service = CrawlRunService(db=db, transnews_client=TransNewsClient())
        result = await service.create_crawl_run(
            user_id=keyword.user_id,
            keyword_ids=[keyword.id],
            force=True,
            custom_start_at=window_start,
            custom_end_at=window_end,
            trigger_type="comparison_backfill",
            capture_social_metrics=False,
            discovery_only=True,
            enrich_for_relevance=True,
        )
        candidates = await _dongguk_articles_for_keyword_date(
            db,
            user_id=keyword.user_id,
            keyword_id=keyword.id,
            mail_date=mail_date,
        )
        article_ids = [item.id for item in candidates if item.id is not None]
        return {
            "mail_date": mail_date,
            "work_window_start": work_window["start_date"].isoformat(),
            "work_window_end": work_window["end_date"].isoformat(),
            "collection_start": window_start.isoformat(),
            "collection_end": window_end.isoformat(),
            "crawl_result": result,
            "candidate_article_ids": article_ids,
        }


async def run_ai(user_id: int, article_ids: list[int], batch_size: int) -> dict:
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
            result = await AutoAiService(db).run_for_articles(user_id=user_id, article_ids=batch)
        for key in totals:
            totals[key] += int(result.get(key) or 0)
        logger.info("AI %s/%s %s", min(offset + len(batch), len(unique_ids)), len(unique_ids), result)
    return {"article_count": len(unique_ids), **totals}


async def main() -> None:
    args = parse_args()
    original = json.loads(args.original_json.read_text(encoding="utf-8"))
    audit_dates = {}
    if args.audit_json and args.audit_json.exists():
        audit_dates = json.loads(args.audit_json.read_text(encoding="utf-8")).get("dates") or {}

    dates = sorted(original["dates"])
    if args.start_date:
        dates = [value for value in dates if date.fromisoformat(value) >= args.start_date]
    if args.end_date:
        dates = [value for value in dates if date.fromisoformat(value) <= args.end_date]
    if audit_dates and not args.include_existing:
        dates = [value for value in dates if not (audit_dates.get(value) or {}).get("candidate_count")]
    if args.limit:
        dates = dates[: args.limit]

    async with AsyncSessionLocal() as db:
        keyword = await db.get(Keyword, args.keyword_id)
        if keyword is None:
            raise SystemExit(f"keyword_id={args.keyword_id} does not exist")
        keyword_snapshot = Keyword(
            id=keyword.id,
            user_id=keyword.user_id,
            keyword_text=keyword.keyword_text,
            email_send_time=keyword.email_send_time,
        )

    progress = {
        "started_at": datetime.now().isoformat(),
        "keyword_id": keyword_snapshot.id,
        "requested_date_count": len(dates),
        "dates": [],
        "failures": [],
    }
    save_progress(args.output, progress)
    all_article_ids: list[int] = []
    progress_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(max(1, args.concurrency))

    async def process_date(index: int, mail_date: str) -> None:
        async with semaphore:
            failure = None
            result = None
            try:
                result = await crawl_mail_date(keyword=keyword_snapshot, mail_date=mail_date)
            except Exception as exc:
                logger.exception("[%s/%s] %s failed", index, len(dates), mail_date)
                failure = {"mail_date": mail_date, "error": str(exc)}

        async with progress_lock:
            if result is not None:
                progress["dates"].append(result)
                all_article_ids.extend(result["candidate_article_ids"])
                crawl = result["crawl_result"]
                logger.info(
                    "[%s/%s] %s run=%s status=%s accepted=%s candidates=%s",
                    index,
                    len(dates),
                    mail_date,
                    crawl.get("crawl_run_id"),
                    crawl.get("status"),
                    crawl.get("crawl_count"),
                    len(result["candidate_article_ids"]),
                )
            if failure is not None:
                progress["failures"].append(failure)
            progress["completed_date_count"] = len(progress["dates"]) + len(progress["failures"])
            progress["dates"].sort(key=lambda item: item["mail_date"])
            progress["failures"].sort(key=lambda item: item["mail_date"])
            save_progress(args.output, progress)

    await asyncio.gather(
        *(process_date(index, mail_date) for index, mail_date in enumerate(dates, start=1))
    )

    if args.run_ai and all_article_ids:
        progress["ai_result"] = await run_ai(
            keyword_snapshot.user_id,
            all_article_ids,
            args.ai_batch_size,
        )
    progress["finished_at"] = datetime.now().isoformat()
    progress["unique_candidate_article_count"] = len(set(all_article_ids))
    save_progress(args.output, progress)
    print(json.dumps({
        "output": str(args.output),
        "requested_dates": len(dates),
        "completed_dates": len(progress["dates"]),
        "failure_count": len(progress["failures"]),
        "unique_candidate_articles": len(set(all_article_ids)),
        "ai_result": progress.get("ai_result"),
    }, ensure_ascii=False))
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(main())
