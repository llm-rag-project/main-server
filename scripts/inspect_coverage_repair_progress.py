import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.models.crawl_run import CrawlRun
from app.models.crawl_run_source import CrawlRunSource


async def main() -> None:
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=6)
    async with AsyncSessionLocal() as db:
        runs = (
            await db.execute(
                select(CrawlRun)
                .join(CrawlRunSource, CrawlRunSource.crawl_run_id == CrawlRun.id)
                .where(
                    CrawlRunSource.trigger_type == "coverage_repair",
                    CrawlRun.created_at >= since,
                )
                .distinct()
                .order_by(CrawlRun.id.desc())
                .limit(50)
            )
        ).scalars().all()

    print(
        json.dumps(
            {
                "run_count": len(runs),
                "runs": [
                    {
                        "id": run.id,
                        "status": run.status,
                        "article_count": run.article_count,
                        "created_at": run.created_at,
                        "finished_at": run.finished_at,
                    }
                    for run in runs
                ],
            },
            ensure_ascii=False,
            default=str,
        )
    )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
