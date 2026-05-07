import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.transnews_client import TransNewsClient
from app.db.session import engine
from app.services.crawl_run_service import CrawlRunService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def run_periodic_crawling() -> None:
    logger.info("정기 크롤링 시작")
    try:
        async with SessionLocal() as db:
            service = CrawlRunService(
                db=db,
                transnews_client=TransNewsClient(),
            )
            result = await service.crawl_active_keywords()
            logger.info("정기 크롤링 종료: %s", result)
    except Exception:
        logger.exception("정기 크롤링 중 오류 발생")


def start_scheduler() -> None:
    if scheduler.running:
        return

    interval_minutes = getattr(settings, "crawl_scheduler_interval_minutes", 30)

    # ✅ 핵심 수정: lambda 제거하고 async 함수를 직접 등록
    scheduler.add_job(
        run_periodic_crawling,          # async def를 그대로 전달
        trigger="interval",
        minutes=interval_minutes,
        id="periodic-crawl-job",
        replace_existing=True,
        misfire_grace_time=60,          # 서버 부하로 실행이 늦어져도 60초 이내면 실행
        max_instances=1,                # 이전 크롤링이 끝나기 전에 중복 실행 방지
    )
    scheduler.start()
    logger.info("크롤링 스케줄러 시작: %s분 간격", interval_minutes)


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)  # ✅ 종료 시 hang 방지
        logger.info("크롤링 스케줄러 종료")