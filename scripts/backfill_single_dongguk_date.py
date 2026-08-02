import asyncio
import json
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.api.v1.reports import _dongguk_report_window, prebuild_dongguk_mail_drafts_for_scheduler
from app.core.transnews_client import TransNewsClient
from app.db.session import AsyncSessionLocal
from app.models.keyword import Keyword
from app.models.user import User
from app.services.auto_ai_service import AutoAiService
from app.services.crawl_run_service import CrawlRunService


async def main() -> None:
    mail_date = os.environ["BACKFILL_DATE"]
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
            raise RuntimeError("동국대 키워드를 찾지 못했습니다.")

        keyword, user = row
        if os.getenv("BACKFILL_FULL_DAY") == "1":
            target_date = datetime.strptime(mail_date, "%Y-%m-%d").date()
            kst = ZoneInfo("Asia/Seoul")
            window_start = datetime.combine(target_date, time.min, tzinfo=kst)
            window_end = datetime.combine(target_date, time.max, tzinfo=kst)
        else:
            window_start, window_end = _dongguk_report_window(mail_date, keyword.email_send_time)
        crawl_service = CrawlRunService(db=db, transnews_client=TransNewsClient())
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
            ai_result = await AutoAiService(db).run_for_crawl_run(
                user_id=user.id,
                crawl_run_id=crawl_run_id,
            )
        draft_result = await prebuild_dongguk_mail_drafts_for_scheduler(
            db,
            mail_date=mail_date,
            user_id=user.id,
            keyword_ids=[keyword.id],
            force_rebuild=True,
        )
        print(
            json.dumps(
                {
                    "mail_date": mail_date,
                    "keyword_id": keyword.id,
                    "user_id": user.id,
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "crawl_result": crawl_result,
                    "ai_result": ai_result,
                    "draft_result": draft_result,
                },
                ensure_ascii=False,
                default=str,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
