import argparse
import asyncio
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path

from app.api.v1.reports import (
    DonggukMailArticle,
    _dedupe_exact_dongguk_articles,
    _dongguk_article_response,
    _dongguk_articles_for_keyword_date,
    _dongguk_mail_section_policy,
    _dongguk_mail_subject,
    _normalize_dongguk_priority_criteria,
    _run_news_editor_or_fallback,
)
from app.db.session import AsyncSessionLocal, engine
from app.models.keyword import Keyword
from app.models.user import User
from app.services.priority_insight_service import PriorityInsightService


logger = logging.getLogger("hongbo-ai-selection")
SECTION_MAP = {
    "foundation": "dongguk_core",
    "education": "education",
    "buddhism": "buddhism",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rerun AI mail selection for historical Hongbo dates.")
    parser.add_argument("--original-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keyword-id", type=int, default=86)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument(
        "--include-original-fallbacks",
        action="store_true",
        help="Diagnostic only: inject missing original-mail rows into the candidate pool.",
    )
    return parser.parse_args()


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def normalized_title(value: str | None) -> str:
    text = str(value or "").lower().replace("동국대학교", "동국대")
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def add_original_fallbacks(
    mail_date: str,
    candidates: list[DonggukMailArticle],
    original_articles: list[dict],
) -> tuple[list[DonggukMailArticle], int]:
    known_urls = {
        link
        for candidate in candidates
        for link in [candidate.url, *(candidate.links or [])]
        if link
    }
    known_titles = {normalized_title(candidate.title) for candidate in candidates}
    result = list(candidates)
    added = 0
    synthetic_base = -int(mail_date.replace("-", "")) * 1000
    for index, original in enumerate(original_articles, start=1):
        original_urls = set(original.get("urls") or [])
        title_key = normalized_title(original.get("title"))
        if original_urls & known_urls or (title_key and title_key in known_titles):
            continue
        links = list(original_urls)
        result.append(
            DonggukMailArticle(
                id=synthetic_base - index,
                title=original.get("title") or "제목 없음",
                source=original.get("source"),
                section=SECTION_MAP.get(original.get("section")),
                summary=None,
                url=links[0] if links else None,
                links=links,
                is_syndicated=bool(original.get("is_syndicated") or len(links) > 1),
                published_at=f"{mail_date}T07:00:00+09:00",
            )
        )
        known_urls.update(original_urls)
        known_titles.add(title_key)
        added += 1
    return result, added


async def main() -> None:
    args = parse_args()
    original = json.loads(args.original_json.read_text(encoding="utf-8"))
    dates = sorted(original["dates"])
    if args.start_date:
        dates = [value for value in dates if date.fromisoformat(value) >= args.start_date]
    if args.end_date:
        dates = [value for value in dates if date.fromisoformat(value) <= args.end_date]

    async with AsyncSessionLocal() as db:
        keyword = await db.get(Keyword, args.keyword_id)
        if keyword is None:
            raise SystemExit(f"keyword_id={args.keyword_id} does not exist")
        user = await db.get(User, keyword.user_id)
        if user is None:
            raise SystemExit(f"user_id={keyword.user_id} does not exist")
        criteria = await PriorityInsightService(db).effective_criteria(
            user_id=user.id,
            keyword_id=keyword.id,
            base_criteria=_normalize_dongguk_priority_criteria(keyword.importance_criteria),
        )
        user_snapshot = User(
            id=user.id,
            email=user.email,
            hashed_password=user.hashed_password,
            name=user.name,
            default_language=user.default_language,
        )
        keyword_snapshot = Keyword(id=keyword.id, user_id=keyword.user_id, email_send_time=keyword.email_send_time)

    output = {
        "started_at": datetime.now().isoformat(),
        "keyword_id": keyword_snapshot.id,
        "requested_date_count": len(dates),
        "priority_criteria": criteria,
        "dates": {},
        "failures": [],
    }
    save(args.output, output)
    semaphore = asyncio.Semaphore(max(1, args.concurrency))
    output_lock = asyncio.Lock()

    async def process(mail_date: str) -> None:
        try:
            async with semaphore:
                async with AsyncSessionLocal() as db:
                    candidates = await _dongguk_articles_for_keyword_date(
                        db,
                        user_id=keyword_snapshot.user_id,
                        keyword_id=keyword_snapshot.id,
                        mail_date=mail_date,
                    )
                db_candidate_count = len(candidates)
                archive_fallback_count = 0
                if args.include_original_fallbacks:
                    candidates, archive_fallback_count = add_original_fallbacks(
                        mail_date,
                        candidates,
                        original["dates"][mail_date]["articles"],
                    )
                deduped, exact_excluded = _dedupe_exact_dongguk_articles(candidates)
                if deduped:
                    selected, ai_excluded, raw = await _run_news_editor_or_fallback(
                        current_user=user_snapshot,
                        mail_date=mail_date,
                        subject=_dongguk_mail_subject(mail_date),
                        articles=deduped,
                        priority_criteria=criteria,
                    )
                    selected, excluded = _dongguk_mail_section_policy(
                        selected,
                        [*ai_excluded, *exact_excluded],
                        candidates,
                        mail_date,
                    )
                else:
                    selected, excluded, raw = [], exact_excluded, None
                result = {
                    "db_candidate_count": db_candidate_count,
                    "archive_fallback_count": archive_fallback_count,
                    "candidate_count": len(candidates),
                    "deduped_candidate_count": len(deduped),
                    "selected_count": len(selected),
                    "excluded_count": len(excluded),
                    "selected_articles": [_dongguk_article_response(item) for item in selected],
                    "excluded_articles": [_dongguk_article_response(item) for item in excluded],
                    "editor_used": raw is not None,
                }
            async with output_lock:
                output["dates"][mail_date] = result
                logger.info(
                    "%s candidates=%s selected=%s excluded=%s",
                    mail_date,
                    result["candidate_count"],
                    result["selected_count"],
                    result["excluded_count"],
                )
                output["completed_date_count"] = len(output["dates"]) + len(output["failures"])
                output["dates"] = dict(sorted(output["dates"].items()))
                save(args.output, output)
        except Exception as exc:
            logger.exception("AI selection failed for %s", mail_date)
            async with output_lock:
                output["failures"].append({"mail_date": mail_date, "error": str(exc)})
                output["completed_date_count"] = len(output["dates"]) + len(output["failures"])
                output["failures"].sort(key=lambda item: item["mail_date"])
                save(args.output, output)

    await asyncio.gather(*(process(mail_date) for mail_date in dates))
    output["finished_at"] = datetime.now().isoformat()
    output["summary"] = {
        "date_count": len(output["dates"]),
        "failure_count": len(output["failures"]),
        "candidate_count": sum(item["candidate_count"] for item in output["dates"].values()),
        "injected_original_fallback_count": sum(
            item["archive_fallback_count"] for item in output["dates"].values()
        ),
        "selected_count": sum(item["selected_count"] for item in output["dates"].values()),
        "excluded_count": sum(item["excluded_count"] for item in output["dates"].values()),
    }
    save(args.output, output)
    print(json.dumps({"output": str(args.output), **output["summary"]}, ensure_ascii=False))
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(main())
