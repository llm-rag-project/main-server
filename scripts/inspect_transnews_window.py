import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.transnews_client import TransNewsClient
from app.services.crawl_run_service import CrawlRunService


KST = ZoneInfo("Asia/Seoul")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mail-date", required=True)
    parser.add_argument("--keyword", default="동국대")
    parser.add_argument("--send-time", default="08:30")
    parser.add_argument("--plain-search", action="store_true")
    parser.add_argument("--output")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    target_date = datetime.strptime(args.mail_date, "%Y-%m-%d").date()
    send_hour, send_minute = map(int, args.send_time.split(":"))
    end_at = datetime.combine(
        target_date,
        time(hour=send_hour, minute=send_minute),
        tzinfo=KST,
    )
    start_at = end_at - timedelta(days=1)

    client = TransNewsClient()
    service = CrawlRunService(db=None, transnews_client=client)
    try:
        response = await client.search_news(
            keyword=args.keyword,
            published_after=start_at.isoformat(),
            published_before=end_at.isoformat(),
            limit=100,
            include_dongguk_official=not args.plain_search,
            include_section_pools=not args.plain_search,
            include_empty_content=True,
            section_pool_target_count=None if args.plain_search else 3,
            timeout_seconds=90,
            discovery_only=True,
            include_source_debug=True,
        )
    finally:
        await TransNewsClient.close_shared_client()

    items = list(response.get("data") or [])
    section_counts = Counter(
        str(item.get("section") or "unclassified").casefold() for item in items
    )
    source_counts = Counter(service._audit_source_name(item) for item in items)
    source_type_counts = Counter(
        str(item.get("source_type") or "unknown") for item in items
    )
    payload = {
        "mail_date": args.mail_date,
        "window_start": start_at.isoformat(),
        "window_end": end_at.isoformat(),
        "status": response.get("status"),
        "item_count": len(items),
        "section_counts": dict(section_counts),
        "audit_source_counts": dict(source_counts),
        "source_type_counts": dict(source_type_counts),
        "source_debug": response.get("source_debug") or {},
        "items": [
            {
                "title": item.get("title"),
                "published_at": (
                    item.get("published_at")
                    or item.get("published")
                    or item.get("pubDate")
                    or item.get("pubdate")
                    or item.get("date")
                ),
                "section": item.get("section"),
                "source_type": item.get("source_type"),
                "collection_source": item.get("collection_source"),
                "audit_source": service._audit_source_name(item),
                "url": service._extract_article_url(item),
            }
            for item in items
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
                    "item_count": len(items),
                    "section_counts": dict(section_counts),
                    "audit_source_counts": dict(source_counts),
                },
                ensure_ascii=False,
            )
        )
    else:
        print(output)


if __name__ == "__main__":
    asyncio.run(main())
