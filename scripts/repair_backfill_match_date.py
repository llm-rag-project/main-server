import asyncio
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update

from app.db.session import AsyncSessionLocal
from app.models.article_match import ArticleMatch


async def main() -> None:
    crawl_run_id = int(os.environ["CRAWL_RUN_ID"])
    keyword_id = int(os.getenv("KEYWORD_ID", "86"))
    target_date = datetime.strptime(os.environ["MATCH_DATE"], "%Y-%m-%d").date()
    matched_at = datetime.combine(target_date, time(hour=12), tzinfo=ZoneInfo("Asia/Seoul"))

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(ArticleMatch)
            .where(ArticleMatch.crawl_run_id == crawl_run_id)
            .values(matched_at=matched_at)
        )
        await db.commit()
        count = await db.scalar(
            select(func.count())
            .select_from(ArticleMatch)
            .where(
                ArticleMatch.crawl_run_id == crawl_run_id,
                func.date(ArticleMatch.matched_at) == target_date,
            )
        )
        dashboard_count = await db.scalar(
            select(func.count())
            .select_from(ArticleMatch)
            .where(
                ArticleMatch.keyword_id == keyword_id,
                func.date(ArticleMatch.matched_at) == target_date,
            )
        )
        print(
            {
                "crawl_run_id": crawl_run_id,
                "target_date": target_date.isoformat(),
                "updated": result.rowcount,
                "verified": count,
                "dashboard_count": dashboard_count,
            }
        )


if __name__ == "__main__":
    asyncio.run(main())
