import argparse
import asyncio
import json
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.api.v1.reports import (
    DONGGUK_MAIL_POLICY_VERSION,
    prebuild_dongguk_mail_drafts_for_scheduler,
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


def save(path: str | None, payload: dict) -> None:
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


async def main() -> None:
    args = parse_args()
    if args.start_date > args.end_date:
        raise SystemExit("start-date must be less than or equal to end-date")

    async with AsyncSessionLocal() as db:
        keyword = await db.get(Keyword, args.keyword_id)
        if keyword is None:
            raise SystemExit(f"keyword {args.keyword_id} was not found")
        keyword_id = int(keyword.id)
        user_id = int(keyword.user_id)

    results: list[dict] = []
    for target_date in iter_dates(args.start_date, args.end_date):
        row = None
        for attempt in range(1, 4):
            try:
                async with AsyncSessionLocal() as db:
                    work_window = await HolidayService(db).work_window(user_id, target_date)
                    row = {
                        "mail_date": target_date.isoformat(),
                        "is_target_business_day": work_window["is_target_business_day"],
                        "attempt": attempt,
                    }
                    if not work_window["is_target_business_day"]:
                        row["status"] = "skipped_non_business_day"
                        break

                    draft = await db.scalar(
                        select(DonggukMailDraft).where(
                            DonggukMailDraft.user_id == user_id,
                            DonggukMailDraft.keyword_id == keyword_id,
                            DonggukMailDraft.mail_date == target_date.isoformat(),
                        )
                    )
                    manual_action_count = len(
                        (
                            await db.execute(
                                select(DonggukPriorityAction.id).where(
                                    DonggukPriorityAction.user_id == user_id,
                                    DonggukPriorityAction.keyword_id == keyword_id,
                                    DonggukPriorityAction.mail_date == target_date.isoformat(),
                                    ~DonggukPriorityAction.source_screen.like("demo_seed_%"),
                                )
                            )
                        ).scalars().all()
                    )
                    row["manual_action_count"] = manual_action_count
                    preview = {}
                    if draft is not None:
                        try:
                            preview = json.loads(draft.preview_body or "{}")
                        except json.JSONDecodeError:
                            preview = {}
                        row["backup"] = {
                            "draft_id": draft.id,
                            "subject": draft.subject,
                            "selected_article_keys": draft.selected_article_keys,
                            "selected_articles": draft.selected_articles,
                            "removed_article_keys": draft.removed_article_keys,
                            "removed_articles": draft.removed_articles,
                            "preview_body": draft.preview_body,
                            "updated_at": draft.updated_at,
                        }
                    if draft is not None and manual_action_count:
                        row["status"] = "preserved_manual_draft"
                        break
                    if preview.get("policy_version") == DONGGUK_MAIL_POLICY_VERSION:
                        row["status"] = "already_current"
                        break

                    result = await prebuild_dongguk_mail_drafts_for_scheduler(
                        db,
                        mail_date=target_date.isoformat(),
                        user_id=user_id,
                        keyword_ids=[keyword_id],
                        force_rebuild=True,
                    )
                    row["result"] = result
                    row["status"] = "rebuilt" if result["built_count"] else "failed"
                    break
            except DBAPIError as exc:
                row = {
                    "mail_date": target_date.isoformat(),
                    "attempt": attempt,
                    "status": "retrying" if attempt < 3 else "failed",
                    "error": str(exc),
                }
                if attempt < 3:
                    await asyncio.sleep(min(2**attempt, 8))

        assert row is not None
        results.append(row)
        save(
            args.output,
            {
                "in_progress": True,
                "completed_date_count": len(results),
                "results": results,
            },
        )

    payload = {
        "in_progress": False,
        "completed_date_count": len(results),
        "rebuilt_count": sum(item["status"] == "rebuilt" for item in results),
        "preserved_manual_count": sum(
            item["status"] == "preserved_manual_draft" for item in results
        ),
        "already_current_count": sum(
            item["status"] == "already_current" for item in results
        ),
        "failed_dates": [
            item["mail_date"] for item in results if item["status"] == "failed"
        ],
        "results": results,
    }
    save(args.output, payload)
    print(json.dumps(payload, ensure_ascii=False, default=str))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
