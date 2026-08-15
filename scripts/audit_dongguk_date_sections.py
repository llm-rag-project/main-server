import argparse
import asyncio
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select

from app.api.v1.reports import (
    _dongguk_articles_for_keyword_date,
    _is_dongguk_mail_section_eligible,
    _dongguk_section_key,
)
from app.db.session import AsyncSessionLocal, engine
from app.models.crawl_run_article import CrawlRunArticle
from app.models.crawl_run_source import CrawlRunSource
from app.models.keyword import Keyword
from app.services.holiday_service import HolidayService, article_collection_window


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--keyword-id", type=int)
    parser.add_argument("--output")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    if start_date > end_date:
        raise SystemExit("start-date must be less than or equal to end-date")

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

        rows = []
        cursor = start_date
        while cursor <= end_date:
            mail_date = cursor.isoformat()
            work_window = await HolidayService(db).work_window(keyword.user_id, cursor)
            published_from, published_to = article_collection_window(
                work_window["start_date"],
                work_window["end_date"],
                keyword.email_send_time or "08:30",
            )
            candidates = await _dongguk_articles_for_keyword_date(
                db,
                user_id=keyword.user_id,
                keyword_id=keyword.id,
                mail_date=mail_date,
            )
            raw_section_counts = Counter(
                _dongguk_section_key(item.section) for item in candidates
            )
            eligible_candidates = [
                item for item in candidates if _is_dongguk_mail_section_eligible(item)
            ]
            section_counts = Counter(
                _dongguk_section_key(item.section) for item in eligible_candidates
            )
            invalid_candidates = [
                item for item in candidates if not _is_dongguk_mail_section_eligible(item)
            ]

            source_rows = (
                await db.execute(
                    select(CrawlRunSource)
                    .where(
                        CrawlRunSource.keyword_id == keyword.id,
                        CrawlRunSource.window_start <= published_to,
                        CrawlRunSource.window_end >= published_from,
                    )
                    .order_by(CrawlRunSource.created_at, CrawlRunSource.id)
                )
            ).scalars().all()
            run_ids = sorted({int(item.crawl_run_id) for item in source_rows})
            audit_rows = []
            if run_ids:
                audit_rows = (
                    await db.execute(
                        select(CrawlRunArticle).where(
                            CrawlRunArticle.crawl_run_id.in_(run_ids),
                            CrawlRunArticle.keyword_id == keyword.id,
                            CrawlRunArticle.published_at >= published_from,
                            CrawlRunArticle.published_at <= published_to,
                        )
                    )
                ).scalars().all()

            source_totals = defaultdict(
                lambda: {
                    "runs": 0,
                    "discovered": 0,
                    "processed": 0,
                    "stored": 0,
                    "duplicates": 0,
                    "rejected_date": 0,
                    "rejected_relevance": 0,
                    "failed": 0,
                    "statuses": Counter(),
                }
            )
            for item in source_rows:
                target = source_totals[item.source_name]
                target["runs"] += 1
                target["discovered"] += int(item.discovered_count or 0)
                target["processed"] += int(item.processed_count or 0)
                target["stored"] += int(item.stored_count or 0)
                target["duplicates"] += int(item.duplicate_count or 0)
                target["rejected_date"] += int(item.rejected_date_count or 0)
                target["rejected_relevance"] += int(item.rejected_relevance_count or 0)
                target["failed"] += int(item.failed_count or 0)
                target["statuses"][item.status] += 1

            audit_counts = Counter(
                f"{item.source_name}:{item.status}:{item.reason_code or '-'}"
                for item in audit_rows
            )
            rows.append(
                {
                    "mail_date": mail_date,
                    "is_target_business_day": work_window["is_target_business_day"],
                    "work_start_date": work_window["start_date"].isoformat(),
                    "holiday_dates": [
                        item.isoformat() for item in work_window.get("holiday_dates", [])
                    ],
                    "published_from": published_from.isoformat(),
                    "published_to": published_to.isoformat(),
                    "candidate_count": len(candidates),
                    "eligible_candidate_count": len(eligible_candidates),
                    "section_counts": {
                        "foundation": section_counts.get("foundation", 0),
                        "education": section_counts.get("education", 0),
                        "buddhism": section_counts.get("buddhism", 0),
                        "unclassified": section_counts.get("unclassified", 0),
                    },
                    "raw_section_counts": {
                        "foundation": raw_section_counts.get("foundation", 0),
                        "education": raw_section_counts.get("education", 0),
                        "buddhism": raw_section_counts.get("buddhism", 0),
                        "unclassified": raw_section_counts.get("unclassified", 0),
                    },
                    "invalid_candidates": [
                        {
                            "id": item.id,
                            "title": item.title,
                            "section": _dongguk_section_key(item.section),
                            "url": item.url,
                        }
                        for item in invalid_candidates
                    ],
                    "run_ids": run_ids,
                    "source_totals": {
                        name: {
                            **{key: value for key, value in totals.items() if key != "statuses"},
                            "statuses": dict(totals["statuses"]),
                        }
                        for name, totals in sorted(source_totals.items())
                    },
                    "candidate_audit": dict(sorted(audit_counts.items())),
                    "education_titles": [
                        item.title
                        for item in eligible_candidates
                        if _dongguk_section_key(item.section) == "education"
                    ],
                    "buddhism_titles": [
                        item.title
                        for item in eligible_candidates
                        if _dongguk_section_key(item.section) == "buddhism"
                    ],
                }
            )
            cursor += timedelta(days=1)

    zero_section_dates_all = {
        section: [
            item["mail_date"]
            for item in rows
            if item["section_counts"][section] == 0
        ]
        for section in ("foundation", "education", "buddhism")
    }
    zero_section_dates_business = {
        section: [
            item["mail_date"]
            for item in rows
            if item["is_target_business_day"]
            and item["section_counts"][section] == 0
        ]
        for section in ("foundation", "education", "buddhism")
    }
    zero_section_dates_non_business = {
        section: [
            item["mail_date"]
            for item in rows
            if not item["is_target_business_day"]
            and item["section_counts"][section] == 0
        ]
        for section in ("foundation", "education", "buddhism")
    }

    payload = {
        "keyword_id": keyword.id,
        "keyword": keyword.keyword_text,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "dates": rows,
        "zero_section_dates": zero_section_dates_business,
        "zero_section_dates_all": zero_section_dates_all,
        "zero_section_dates_non_business": zero_section_dates_non_business,
    }
    output = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as file:
            file.write(output)
    if args.output:
        print(
            json.dumps(
                {
                    "output": args.output,
                    "keyword_id": keyword.id,
                    "date_count": len(rows),
                    "zero_section_dates": payload["zero_section_dates"],
                    "zero_section_dates_non_business": payload[
                        "zero_section_dates_non_business"
                    ],
                },
                ensure_ascii=False,
            )
        )
    else:
        print(output)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
