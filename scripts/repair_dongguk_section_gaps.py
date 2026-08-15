import argparse
import asyncio
import json
import logging
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.api.v1.reports import (
    _dongguk_articles_for_keyword_date,
    _is_dongguk_mail_section_eligible,
    _dongguk_section_key,
    prebuild_dongguk_mail_drafts_for_scheduler,
)
from app.core.transnews_client import TransNewsClient
from app.db.session import AsyncSessionLocal, engine
from app.models.keyword import Keyword
from app.services.auto_ai_service import AutoAiService
from app.services.crawl_run_service import CrawlRunService
from app.services.holiday_service import HolidayService, article_collection_window


SECTIONS = ("foundation", "education", "buddhism")
logger = logging.getLogger("dongguk-section-repair")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--keyword-id", type=int)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--include-non-business-days", action="store_true")
    parser.add_argument("--output")
    return parser.parse_args()


def iter_dates(start_date: date, end_date: date):
    cursor = start_date
    while cursor <= end_date:
        yield cursor
        cursor += timedelta(days=1)


def save_progress(path: str | None, payload: dict) -> None:
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def progress_payload(
    *,
    keyword_id: int,
    start_date: date,
    end_date: date,
    results: list[dict],
) -> dict:
    return {
        "keyword_id": keyword_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "in_progress": True,
        "completed_date_count": len(results),
        "results": results,
    }


async def section_counts(
    *,
    user_id: int,
    keyword_id: int,
    mail_date: str,
) -> dict[str, int]:
    last_error: DBAPIError | None = None
    for attempt in range(1, 4):
        try:
            async with AsyncSessionLocal() as audit_db:
                articles = await _dongguk_articles_for_keyword_date(
                    audit_db,
                    user_id=user_id,
                    keyword_id=keyword_id,
                    mail_date=mail_date,
                )
            counts = Counter(
                _dongguk_section_key(item.section)
                for item in articles
                if _is_dongguk_mail_section_eligible(item)
            )
            return {section: counts.get(section, 0) for section in SECTIONS}
        except DBAPIError as exc:
            last_error = exc
            logger.warning(
                "Section audit query failed date=%s attempt=%s/3; retrying",
                mail_date,
                attempt,
            )
            if attempt < 3:
                await asyncio.sleep(min(2**attempt, 8))
    assert last_error is not None
    raise last_error


async def main() -> None:
    args = parse_args()
    if args.start_date > args.end_date:
        raise SystemExit("start-date must be less than or equal to end-date")
    if not 1 <= args.max_attempts <= 3:
        raise SystemExit("max-attempts must be between 1 and 3")

    results = []
    async with AsyncSessionLocal() as db:
        if args.keyword_id:
            keyword = await db.get(Keyword, args.keyword_id)
        else:
            keyword = (
                await db.execute(
                    select(Keyword)
                    .where(Keyword.keyword_text.ilike("%동국%"))
                    .order_by(Keyword.id)
                    .limit(1)
                )
            ).scalar_one_or_none()
        if keyword is None:
            raise SystemExit("Dongguk keyword was not found")

        keyword_id = int(keyword.id)
        user_id = int(keyword.user_id)
        email_send_time = keyword.email_send_time or "08:30"

        crawl_service = CrawlRunService(db=db, transnews_client=TransNewsClient())
        holiday_service = HolidayService(db)
        for target_date in iter_dates(args.start_date, args.end_date):
            mail_date = target_date.isoformat()
            work_window = await holiday_service.work_window(user_id, target_date)
            before = await section_counts(
                user_id=user_id,
                keyword_id=keyword_id,
                mail_date=mail_date,
            )
            missing_before = [section for section in SECTIONS if before[section] == 0]
            row = {
                "mail_date": mail_date,
                "is_target_business_day": work_window["is_target_business_day"],
                "before": before,
                "missing_before": missing_before,
                "attempts": [],
            }
            if not missing_before:
                row["status"] = "already_complete"
                row["after"] = before
                results.append(row)
                save_progress(
                    args.output,
                    progress_payload(
                        keyword_id=keyword_id,
                        start_date=args.start_date,
                        end_date=args.end_date,
                        results=results,
                    ),
                )
                continue
            if (
                not work_window["is_target_business_day"]
                and not args.include_non_business_days
            ):
                row["status"] = "skipped_non_business_day"
                row["after"] = before
                results.append(row)
                save_progress(
                    args.output,
                    progress_payload(
                        keyword_id=keyword_id,
                        start_date=args.start_date,
                        end_date=args.end_date,
                        results=results,
                    ),
                )
                continue

            window_start, window_end = article_collection_window(
                work_window["start_date"],
                work_window["end_date"],
                email_send_time,
            )
            after = before
            for attempt in range(1, args.max_attempts + 1):
                try:
                    crawl_result = await crawl_service.create_crawl_run(
                        user_id=user_id,
                        keyword_ids=[keyword_id],
                        force=True,
                        custom_start_at=window_start,
                        custom_end_at=window_end,
                        trigger_type="coverage_repair",
                        capture_social_metrics=False,
                        discovery_only=True,
                        enrich_for_relevance=True,
                        section_pool_target_count=10,
                        search_sort="latest",
                    )
                    ai_result = None
                    ai_error = None
                    if crawl_result.get("crawl_run_id"):
                        try:
                            ai_result = await AutoAiService(db).run_for_crawl_run(
                                user_id=user_id,
                                crawl_run_id=crawl_result["crawl_run_id"],
                            )
                        except Exception as exc:
                            await db.rollback()
                            ai_error = str(exc)
                            logger.exception(
                                "AI repair failed date=%s run_id=%s",
                                mail_date,
                                crawl_result.get("crawl_run_id"),
                            )
                    after = await section_counts(
                        user_id=user_id,
                        keyword_id=keyword_id,
                        mail_date=mail_date,
                    )
                    row["attempts"].append(
                        {
                            "attempt": attempt,
                            "crawl_run_id": crawl_result.get("crawl_run_id"),
                            "crawl_status": crawl_result.get("status"),
                            "crawl_count": crawl_result.get("crawl_count"),
                            "ai_result": ai_result,
                            "ai_error": ai_error,
                            "section_counts": after,
                        }
                    )
                except Exception as exc:
                    await db.rollback()
                    row["attempts"].append(
                        {
                            "attempt": attempt,
                            "error": str(exc),
                            "section_counts": after,
                        }
                    )
                    logger.exception(
                        "Collection repair failed date=%s attempt=%s",
                        mail_date,
                        attempt,
                    )
                if all(after[section] > 0 for section in SECTIONS):
                    break
                if attempt < args.max_attempts:
                    await asyncio.sleep(min(2**attempt, 8))

            try:
                await prebuild_dongguk_mail_drafts_for_scheduler(
                    db,
                    mail_date=mail_date,
                    user_id=user_id,
                    keyword_ids=[keyword_id],
                    force_rebuild=True,
                )
            except Exception as exc:
                await db.rollback()
                row["draft_error"] = str(exc)
                logger.exception("Draft rebuild failed date=%s", mail_date)
            row["after"] = after
            row["status"] = (
                "repaired"
                if all(after[section] > 0 for section in SECTIONS)
                else "still_incomplete"
            )
            results.append(row)
            save_progress(
                args.output,
                progress_payload(
                    keyword_id=keyword_id,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    results=results,
                ),
            )

    payload = {
        "keyword_id": keyword_id,
        "start_date": args.start_date.isoformat(),
        "end_date": args.end_date.isoformat(),
        "in_progress": False,
        "completed_date_count": len(results),
        "results": results,
        "summary": dict(Counter(item["status"] for item in results)),
        "still_incomplete_dates": [
            item["mail_date"]
            for item in results
            if item["status"] == "still_incomplete"
        ],
    }
    output = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as file:
            file.write(output)
        print(
            json.dumps(
                {
                    "output": args.output,
                    "summary": payload["summary"],
                    "still_incomplete_dates": payload["still_incomplete_dates"],
                },
                ensure_ascii=False,
            )
        )
    else:
        print(output)
    await TransNewsClient.close_shared_client()
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
