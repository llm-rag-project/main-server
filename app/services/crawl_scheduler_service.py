import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.transnews_client import TransNewsClient
from app.db.session import engine
from app.models.keyword import Keyword
from app.repositories.stats_repository import StatsRepository
from app.services.analysis_service import AnalysisService
from app.services.auto_ai_service import AutoAiService
from app.services.crawl_run_service import CrawlRunService
from app.services.stats_service import StatsService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def run_periodic_crawling() -> None:
    logger.info("Periodic crawling started")
    try:
        async with SessionLocal() as db:
            service = CrawlRunService(
                db=db,
                transnews_client=TransNewsClient(),
            )
            result = await service.crawl_all_active_keywords()
            for item in result.get("runs", []):
                if item.get("crawl_run_id"):
                    auto_result = await AutoAiService(db).run_for_crawl_run(
                        user_id=item["user_id"],
                        crawl_run_id=item["crawl_run_id"],
                    )
                    logger.info("Auto summary/importance finished: %s", auto_result)
            logger.info("Periodic crawling finished: %s", result)
    except Exception:
        logger.exception("Periodic crawling failed")
        return

    logger.info("AI analysis batch started")
    try:
        async with SessionLocal() as db:
            analysis_service = AnalysisService(db)
            analysis_result = await analysis_service.run_analysis()
            logger.info("AI analysis batch finished: %s", analysis_result)
    except Exception:
        logger.exception("AI analysis batch failed")


async def capture_hourly_news_search_metrics() -> None:
    logger.info("Hourly news search metric capture started")
    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(Keyword.user_id)
                .where(Keyword.is_active.is_(True))
                .distinct()
            )
            user_ids = [int(row[0]) for row in result.all()]
            total_captured = 0
            total_failed = 0

            for user_id in user_ids:
                service = StatsService(
                    repo=StatsRepository(db),
                    transnews_client=TransNewsClient(),
                )
                capture_result = await service.capture_news_search_metrics(user_id=user_id)
                total_captured += capture_result.get("captured_count", 0)
                total_failed += capture_result.get("failed_count", 0)

            await db.commit()
            logger.info(
                "Hourly news search metric capture finished: captured=%s failed=%s users=%s",
                total_captured,
                total_failed,
                len(user_ids),
            )
    except Exception:
        logger.exception("Hourly news search metric capture failed")


def start_scheduler() -> None:
    if scheduler.running:
        return

    scheduler.add_job(
        run_periodic_crawling,
        trigger="cron",
        hour=8,
        minute=0,
        timezone="Asia/Seoul",
        id="periodic-crawl-job",
        replace_existing=True,
        misfire_grace_time=600,
        max_instances=1,
    )
    scheduler.add_job(
        capture_hourly_news_search_metrics,
        trigger="cron",
        minute=0,
        timezone="Asia/Seoul",
        id="hourly-news-search-metrics-job",
        replace_existing=True,
        misfire_grace_time=600,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started: daily crawl at 08:00 KST, hourly news search metrics")


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
