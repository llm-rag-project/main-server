import argparse
import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.models.crawl_run_source import CrawlRunSource


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("crawl_run_id", type=int)
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(CrawlRunSource)
                .where(CrawlRunSource.crawl_run_id == args.crawl_run_id)
                .order_by(CrawlRunSource.id)
            )
        ).scalars().all()
        for row in rows:
            print(
                {
                    "source": row.source_name,
                    "status": row.status,
                    "discovered": row.discovered_count,
                    "processed": row.processed_count,
                    "stored": row.stored_count,
                    "duplicates": row.duplicate_count,
                    "rejected_date": row.rejected_date_count,
                    "retry": row.retry_count,
                    "error": (row.error_message or "")[:160],
                }
            )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
