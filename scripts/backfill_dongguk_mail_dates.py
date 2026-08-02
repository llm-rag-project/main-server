import asyncio
import json
import os

from app.api.v1.reports import _dongguk_report_window, prebuild_dongguk_mail_drafts_for_scheduler
from app.core.transnews_client import TransNewsClient
from app.db.session import AsyncSessionLocal
from app.models.keyword import Keyword
from app.models.user import User
from app.services.auto_ai_service import AutoAiService
from app.services.crawl_run_service import CrawlRunService
from sqlalchemy import select


DATES = [
    value.strip()
    for value in os.getenv(
        "BACKFILL_DATES",
        "2026-07-13,2026-07-14,2026-07-15,2026-07-16,2026-07-17,2026-07-20,2026-07-21",
    ).split(",")
    if value.strip()
]


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Keyword, User)
            .join(User, User.id == Keyword.user_id)
            .where(Keyword.keyword_text.ilike("%동국%"))
            .order_by(Keyword.id.asc())
            .limit(1)
        )
        row = result.first()
        if not row:
            raise RuntimeError("동국 키워드를 찾지 못했습니다.")

        keyword, user = row
        crawl_service = CrawlRunService(db=db, transnews_client=TransNewsClient())
        auto_ai = AutoAiService(db)
        runs = []

        for mail_date in DATES:
            window_start, window_end = _dongguk_report_window(mail_date, keyword.email_send_time)
            crawl_result = await crawl_service.create_crawl_run(
                user_id=user.id,
                keyword_ids=[keyword.id],
                force=True,
                custom_start_at=window_start,
                custom_end_at=window_end,
            )
            crawl_run_id = crawl_result.get("crawl_run_id")
            ai_result = None
            if crawl_run_id:
                ai_result = await auto_ai.run_for_crawl_run(user_id=user.id, crawl_run_id=crawl_run_id)
            draft_result = await prebuild_dongguk_mail_drafts_for_scheduler(
                db,
                mail_date=mail_date,
                user_id=user.id,
                keyword_ids=[keyword.id],
                force_rebuild=True,
            )
            runs.append({
                "mail_date": mail_date,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "crawl_result": crawl_result,
                "ai_result": ai_result,
                "draft_result": draft_result,
            })

        print(json.dumps({"keyword_id": keyword.id, "user_id": user.id, "runs": runs}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())
