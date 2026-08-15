import argparse
import asyncio
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select

from app.api.v1.reports import (
    DONGGUK_MAIL_POLICY_VERSION,
    DonggukMailArticle,
    _dongguk_section_key,
    _is_dongguk_mail_section_eligible,
    _normalize_dongguk_section_limits,
    _sanitize_dongguk_mail_articles,
)
from app.db.session import AsyncSessionLocal, engine
from app.models.dongguk_mail_draft import DonggukMailDraft
from app.models.dongguk_priority_action import DonggukPriorityAction
from app.models.keyword import Keyword
from app.services.holiday_service import HolidayService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--keyword-id", type=int, required=True)
    parser.add_argument("--output")
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


async def main() -> None:
    args = parse_args()
    if args.start_date > args.end_date:
        raise SystemExit("start-date must be less than or equal to end-date")

    async with AsyncSessionLocal() as db:
        keyword = await db.get(Keyword, args.keyword_id)
        if keyword is None:
            raise SystemExit(f"keyword {args.keyword_id} was not found")
        actions = (
            await db.execute(
                select(DonggukPriorityAction).where(
                    DonggukPriorityAction.user_id == keyword.user_id,
                    DonggukPriorityAction.keyword_id == keyword.id,
                    DonggukPriorityAction.mail_date >= args.start_date.isoformat(),
                    DonggukPriorityAction.mail_date <= args.end_date.isoformat(),
                )
            )
        ).scalars().all()
        action_counts = Counter(
            item.mail_date
            for item in actions
            if item.mail_date and not item.source_screen.startswith("demo_seed_")
        )
        demo_action_counts = Counter(
            item.mail_date
            for item in actions
            if item.mail_date and item.source_screen.startswith("demo_seed_")
        )
        actions_by_date: dict[str, list[dict]] = {}
        for item in actions:
            if not item.mail_date:
                continue
            actions_by_date.setdefault(item.mail_date, []).append(
                {
                    "action_type": item.action_type,
                    "article_title": item.article_title,
                    "article_category": item.article_category,
                    "reason": item.reason,
                    "source_screen": item.source_screen,
                }
            )
        holiday_service = HolidayService(db)
        rows = []
        for target_date in iter_dates(args.start_date, args.end_date):
            mail_date = target_date.isoformat()
            work_window = await holiday_service.work_window(keyword.user_id, target_date)
            draft = await db.scalar(
                select(DonggukMailDraft).where(
                    DonggukMailDraft.user_id == keyword.user_id,
                    DonggukMailDraft.keyword_id == keyword.id,
                    DonggukMailDraft.mail_date == mail_date,
                )
            )
            row = {
                "mail_date": mail_date,
                "is_target_business_day": work_window["is_target_business_day"],
                "found": draft is not None,
                "manual_action_count": action_counts.get(mail_date, 0),
                "demo_action_count": demo_action_counts.get(mail_date, 0),
                "manual_actions": actions_by_date.get(mail_date, []),
            }
            if draft is not None:
                selected = [
                    DonggukMailArticle(**item)
                    for item in loads(draft.selected_articles, [])
                    if isinstance(item, dict)
                ]
                preview = loads(draft.preview_body, {})
                limits = _normalize_dongguk_section_limits(preview.get("section_limits"))
                sanitized, removed = _sanitize_dongguk_mail_articles(selected, limits)
                invalid = [
                    item for item in selected if not _is_dongguk_mail_section_eligible(item)
                ]
                counts = Counter(_dongguk_section_key(item.section) for item in sanitized)
                row.update(
                    {
                        "policy_version": preview.get("policy_version"),
                        "policy_stale": preview.get("policy_version") != DONGGUK_MAIL_POLICY_VERSION,
                        "selected_count": len(selected),
                        "sanitized_count": len(sanitized),
                        "removed_by_current_rules_count": len(removed),
                        "invalid_selected_count": len(invalid),
                        "removed_by_current_rules": [
                            {
                                "title": item.title,
                                "reason": item.selection_reason,
                            }
                            for item in removed
                        ],
                        "section_counts": {
                            section: counts.get(section, 0)
                            for section in ("foundation", "education", "buddhism")
                        },
                        "invalid_selected_titles": [item.title for item in invalid],
                    }
                )
            rows.append(row)

    payload = {
        "policy_version": DONGGUK_MAIL_POLICY_VERSION,
        "date_count": len(rows),
        "business_date_count": sum(item["is_target_business_day"] for item in rows),
        "missing_business_drafts": [
            item["mail_date"]
            for item in rows
            if item["is_target_business_day"] and not item["found"]
        ],
        "stale_business_drafts": [
            item["mail_date"]
            for item in rows
            if item["is_target_business_day"] and item.get("policy_stale")
        ],
        "manual_business_drafts": [
            item["mail_date"]
            for item in rows
            if item["is_target_business_day"] and item["manual_action_count"]
        ],
        "invalid_business_drafts": [
            item["mail_date"]
            for item in rows
            if item["is_target_business_day"] and item.get("invalid_selected_count")
        ],
        "rule_violation_business_drafts": [
            item["mail_date"]
            for item in rows
            if item["is_target_business_day"] and item.get("removed_by_current_rules_count")
        ],
        "dates": rows,
    }
    output = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
        print(
            json.dumps(
                {key: value for key, value in payload.items() if key != "dates"},
                ensure_ascii=False,
            )
        )
    else:
        print(output)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
