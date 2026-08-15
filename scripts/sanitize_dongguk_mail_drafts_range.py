import argparse
import asyncio
import json
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select

from app.api.v1.reports import (
    DonggukMailArticle,
    _dedupe_exact_dongguk_articles,
    _dongguk_article_key,
    _dongguk_article_response,
    _normalize_dongguk_section_limits,
    _sanitize_dongguk_mail_articles,
)
from app.db.session import AsyncSessionLocal, engine
from app.models.dongguk_mail_draft import DonggukMailDraft
from app.models.keyword import Keyword


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--keyword-id", type=int, required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def iter_dates(start_date: date, end_date: date):
    cursor = start_date
    while cursor <= end_date:
        yield cursor
        cursor += timedelta(days=1)


def loads(value: str | None, default):
    try:
        return json.loads(value) if value else default
    except (json.JSONDecodeError, TypeError):
        return default


def dump_models(items: list[DonggukMailArticle]) -> str:
    return json.dumps([item.model_dump() for item in items], ensure_ascii=False)


async def main() -> None:
    args = parse_args()
    if args.start_date > args.end_date:
        raise SystemExit("start-date must be less than or equal to end-date")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as db:
        keyword = await db.get(Keyword, args.keyword_id)
        if keyword is None:
            raise SystemExit(f"keyword {args.keyword_id} was not found")

        rows: list[dict] = []
        for target_date in iter_dates(args.start_date, args.end_date):
            mail_date = target_date.isoformat()
            draft = await db.scalar(
                select(DonggukMailDraft).where(
                    DonggukMailDraft.user_id == keyword.user_id,
                    DonggukMailDraft.keyword_id == keyword.id,
                    DonggukMailDraft.mail_date == mail_date,
                )
            )
            if draft is None:
                rows.append({"mail_date": mail_date, "status": "missing"})
                continue

            selected = [
                DonggukMailArticle(**item)
                for item in loads(draft.selected_articles, [])
                if isinstance(item, dict)
            ]
            preview = loads(draft.preview_body, {})
            limits = _normalize_dongguk_section_limits(preview.get("section_limits"))
            sanitized, newly_removed = _sanitize_dongguk_mail_articles(selected, limits)
            if not newly_removed:
                rows.append(
                    {
                        "mail_date": mail_date,
                        "status": "unchanged",
                        "selected_count": len(selected),
                    }
                )
                continue

            existing_removed = [
                DonggukMailArticle(**item)
                for item in loads(draft.removed_articles, [])
                if isinstance(item, dict)
            ]
            removed, _ = _dedupe_exact_dongguk_articles(
                [*existing_removed, *newly_removed]
            )
            backup = {
                "draft_id": draft.id,
                "selected_article_keys": draft.selected_article_keys,
                "selected_articles": draft.selected_articles,
                "removed_article_keys": draft.removed_article_keys,
                "removed_articles": draft.removed_articles,
                "preview_body": draft.preview_body,
            }

            preview["articles"] = [
                _dongguk_article_response(item) for item in sanitized
            ]
            preview["excluded_articles"] = [
                _dongguk_article_response(item) for item in removed
            ]
            preview["article_count"] = len(sanitized)
            preview["excluded_count"] = len(removed)
            preview["section_limits"] = limits

            draft.selected_article_keys = json.dumps(
                [
                    _dongguk_article_key(item, index)
                    for index, item in enumerate(sanitized)
                ],
                ensure_ascii=False,
            )
            draft.selected_articles = dump_models(sanitized)
            draft.removed_article_keys = json.dumps(
                [
                    _dongguk_article_key(item, index)
                    for index, item in enumerate(removed)
                ],
                ensure_ascii=False,
            )
            draft.removed_articles = dump_models(removed)
            draft.preview_body = json.dumps(preview, ensure_ascii=False)
            await db.commit()

            rows.append(
                {
                    "mail_date": mail_date,
                    "status": "sanitized",
                    "before_count": len(selected),
                    "after_count": len(sanitized),
                    "removed_titles": [item.title for item in newly_removed],
                    "backup": backup,
                }
            )

    payload = {
        "date_count": len(rows),
        "sanitized_count": sum(item["status"] == "sanitized" for item in rows),
        "missing_dates": [item["mail_date"] for item in rows if item["status"] == "missing"],
        "dates": rows,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {key: value for key, value in payload.items() if key != "dates"},
            ensure_ascii=False,
        )
    )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
