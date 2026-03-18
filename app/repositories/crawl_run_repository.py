from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_run import CrawlRun
from app.models.crawl_run_keyword import CrawlRunKeyword


async def create_crawl_run(
    db: AsyncSession,
    user_id: int,
    force_run: bool,
) -> CrawlRun:
    run = CrawlRun(
        user_id=user_id,
        status="QUEUED",
        force_run=force_run,
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    return run


async def add_crawl_run_keywords(
    db: AsyncSession,
    crawl_run_id: int,
    keyword_ids: list[int],
) -> None:
    for keyword_id in keyword_ids:
        db.add(
            CrawlRunKeyword(
                crawl_run_id=crawl_run_id,
                keyword_id=keyword_id,
            )
        )
    await db.flush()


async def get_crawl_run_by_id(
    db: AsyncSession,
    run_id: int,
) -> CrawlRun | None:
    result = await db.execute(
        select(CrawlRun).where(CrawlRun.id == run_id)
    )
    return result.scalar_one_or_none()