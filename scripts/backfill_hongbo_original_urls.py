import argparse
import asyncio
import json
import logging
import re
from datetime import date, datetime, time, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select

from app.core.transnews_client import TransNewsClient
from app.db.session import AsyncSessionLocal, engine
from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.keyword import Keyword
from app.models.summary import Summary
from app.services.article_identity import canonicalize_article_url, content_fingerprint
from app.services.auto_ai_service import AutoAiService


KST = ZoneInfo("Asia/Seoul")
SECTION_MAP = {
    "foundation": "dongguk_core",
    "education": "education",
    "buddhism": "buddhism",
}
logger = logging.getLogger("hongbo-original-url-backfill")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill original Hongbo mail URLs for a controlled historical comparison."
    )
    parser.add_argument("--original-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keyword-id", type=int, default=86)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--fetch-timeout", type=float, default=20.0)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--skip-ai", action="store_true")
    parser.add_argument("--ai-batch-size", type=int, default=100)
    return parser.parse_args()


def clean_text(value, limit: int | None = None) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit] if limit else text


def parsed_datetime(data: dict, fallback_date: date) -> datetime:
    raw = next(
        (
            data.get(key)
            for key in ("published_at", "published", "pubDate", "pubdate", "date")
            if data.get(key)
        ),
        None,
    )
    if raw:
        value = str(raw).strip()
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(value)
            except (TypeError, ValueError, OverflowError):
                parsed = None
        if parsed is not None:
            return parsed.replace(tzinfo=KST) if parsed.tzinfo is None else parsed
    # The archive proves the article was included in that morning's mail even if
    # the source no longer exposes its original timestamp.
    return datetime.combine(fallback_date, time(hour=7), tzinfo=KST)


def thumbnail_url(data: dict) -> str | None:
    values = [
        data.get("thumbnail_url"),
        data.get("thumbnail"),
        data.get("image_url"),
        data.get("image"),
        data.get("og_image"),
    ]
    images = data.get("images")
    if isinstance(images, list):
        values.extend(images)
    for value in values:
        if isinstance(value, dict):
            value = value.get("url") or value.get("src")
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value.strip()
    return None


def extract_summary(content: str, title: str) -> str:
    text = clean_text(content or title)
    sentences = [item.strip() for item in re.split(r"(?<=[.!?다요])\s+", text) if item.strip()]
    summary = " ".join(sentences[:2]) or title
    return summary[:500]


async def fetch_original(
    item: dict,
    semaphore: asyncio.Semaphore,
    fetch_timeout: float,
) -> dict:
    url = next(iter(item.get("urls") or []), "")
    result = {"mail_date": item["mail_date"], "original": item, "url": url}
    if not url:
        result.update({"status": "missing_url", "data": {}})
        return result
    async with semaphore:
        try:
            response = await asyncio.wait_for(
                TransNewsClient().crawl_article(url),
                timeout=max(1.0, fetch_timeout),
            )
            data = response.get("data") or response
            if not isinstance(data, dict):
                data = {}
            result.update({"status": "fetched", "data": data})
        except Exception as exc:
            result.update({"status": "fetch_failed", "data": {}, "error": str(exc)})
    return result


async def upsert_results(keyword: Keyword, fetched: list[dict]) -> tuple[list[int], dict]:
    article_ids: list[int] = []
    counts = {
        "created": 0,
        "updated": 0,
        "matched": 0,
        "summary_created": 0,
        "fallback": 0,
        "failed": 0,
    }
    async with AsyncSessionLocal() as db:
        for index, item in enumerate(fetched, start=1):
            original = item["original"]
            data = item.get("data") or {}
            input_url = item.get("url") or ""
            if not input_url:
                counts["failed"] += 1
                continue
            resolved_url = clean_text(
                data.get("url") or data.get("original_url") or data.get("article_url") or input_url
            )
            canonical_url = canonicalize_article_url(resolved_url)
            title = clean_text(data.get("title") or data.get("headline") or original.get("title") or "제목 없음")
            publisher = clean_text(
                data.get("publisher")
                or data.get("source")
                or data.get("source_name")
                or data.get("media")
                or original.get("source"),
                255,
            ) or None
            content = clean_text(
                data.get("content")
                or data.get("body")
                or data.get("article_content")
                or data.get("text")
                or data.get("summary")
                or data.get("description")
                or title
            )
            if item["status"] != "fetched":
                counts["fallback"] += 1

            existing = (
                await db.execute(
                    select(Article)
                    .where(
                        or_(
                            Article.url == input_url,
                            Article.url == resolved_url,
                            Article.canonical_url == canonical_url,
                        )
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing is None:
                existing = Article(
                    source_type="HONGBO_ARCHIVE_BACKFILL",
                    source_article_id=None,
                    url=resolved_url,
                    canonical_url=canonical_url,
                    content_fingerprint=content_fingerprint(content),
                    title=title,
                    publisher=publisher,
                    collection_source="hongbo_archive_backfill",
                    published_at=parsed_datetime(data, date.fromisoformat(item["mail_date"])),
                    thumbnail_url=thumbnail_url(data),
                    content=content,
                    language=data.get("language") or "ko",
                    section=SECTION_MAP.get(original.get("section")),
                )
                db.add(existing)
                await db.flush()
                counts["created"] += 1
            else:
                if content and (not existing.content or len(content) > len(existing.content)):
                    existing.content = content
                existing.canonical_url = existing.canonical_url or canonical_url
                existing.publisher = existing.publisher or publisher
                existing.published_at = existing.published_at or parsed_datetime(
                    data, date.fromisoformat(item["mail_date"])
                )
                existing.section = existing.section or SECTION_MAP.get(original.get("section"))
                existing.thumbnail_url = existing.thumbnail_url or thumbnail_url(data)
                counts["updated"] += 1

            match = (
                await db.execute(
                    select(ArticleMatch).where(
                        ArticleMatch.article_id == existing.id,
                        ArticleMatch.keyword_id == keyword.id,
                    )
                )
            ).scalar_one_or_none()
            if match is None:
                db.add(ArticleMatch(article_id=existing.id, keyword_id=keyword.id, crawl_run_id=None))
                counts["matched"] += 1
            has_summary = (
                await db.execute(
                    select(Summary.id)
                    .where(Summary.article_id == existing.id, Summary.language == "ko")
                    .limit(1)
                )
            ).scalar_one_or_none()
            if has_summary is None:
                db.add(
                    Summary(
                        article_id=existing.id,
                        language="ko",
                        summary_text=extract_summary(content, title),
                        model_name="hongbo-archive-extract",
                    )
                )
                counts["summary_created"] += 1
            article_ids.append(existing.id)
            if index % 25 == 0:
                await db.commit()
        await db.commit()
    return list(dict.fromkeys(article_ids)), counts


async def run_ai(user_id: int, article_ids: list[int], batch_size: int) -> dict:
    totals = {"summary_count": 0, "importance_count": 0, "already_scored_count": 0, "remaining_count": 0}
    for offset in range(0, len(article_ids), batch_size):
        async with AsyncSessionLocal() as db:
            result = await AutoAiService(db).run_for_articles(
                user_id=user_id,
                article_ids=article_ids[offset : offset + batch_size],
            )
        for key in totals:
            totals[key] += int(result.get(key) or 0)
        logger.info("AI %s/%s", min(offset + batch_size, len(article_ids)), len(article_ids))
    return totals


async def main() -> None:
    args = parse_args()
    payload = json.loads(args.original_json.read_text(encoding="utf-8"))
    originals = []
    for mail_date, document in sorted(payload["dates"].items()):
        target = date.fromisoformat(mail_date)
        if args.start_date and target < args.start_date:
            continue
        if args.end_date and target > args.end_date:
            continue
        originals.extend(document["articles"])

    async with AsyncSessionLocal() as db:
        keyword = await db.get(Keyword, args.keyword_id)
        if keyword is None:
            raise SystemExit(f"keyword_id={args.keyword_id} does not exist")
        snapshot = Keyword(id=keyword.id, user_id=keyword.user_id, keyword_text=keyword.keyword_text)

    semaphore = asyncio.Semaphore(max(1, args.concurrency))
    completed = 0
    completed_lock = asyncio.Lock()

    async def tracked_fetch(item: dict) -> dict:
        nonlocal completed
        result = await fetch_original(item, semaphore, args.fetch_timeout)
        async with completed_lock:
            completed += 1
            if completed % 25 == 0 or completed == len(originals):
                logger.info("URL fetch %s/%s", completed, len(originals))
        return result

    fetched = await asyncio.gather(
        *(tracked_fetch(item) for item in originals)
    )
    article_ids, counts = await upsert_results(snapshot, fetched)
    ai_result = None if args.skip_ai else await run_ai(snapshot.user_id, article_ids, args.ai_batch_size)
    output = {
        "started_count": len(originals),
        "fetch_counts": {
            status: sum(item["status"] == status for item in fetched)
            for status in sorted({item["status"] for item in fetched})
        },
        "database_counts": counts,
        "unique_article_count": len(article_ids),
        "ai_result": ai_result,
        "items": [
            {
                "mail_date": item["mail_date"],
                "title": item["original"].get("title"),
                "url": item.get("url"),
                "status": item["status"],
                "error": item.get("error"),
            }
            for item in fetched
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in output.items() if key != "items"}, ensure_ascii=False))
    await TransNewsClient.close_shared_client()
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(main())
