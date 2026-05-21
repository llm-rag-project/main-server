import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.transnews_client import TransNewsClient
from app.db.session import engine
from app.services.analysis_service import AnalysisService
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
            result = await service.crawl_all_active_keywords()
            logger.info("정기 크롤링 종료: %s", result)
    except Exception:
        logger.exception("정기 크롤링 중 오류 발생")
        return  # 크롤링 실패 시 분석 건너뜀

    # ── 크롤링 완료 후 AI 분석 자동 실행 ──────────────────────
    logger.info("AI 감성/홍보성 분석 배치 시작")
    try:
        async with SessionLocal() as db:
            analysis_service = AnalysisService(db)
            analysis_result = await analysis_service.run_analysis()
            logger.info("AI 분석 완료: %s", analysis_result)
    except Exception:
        logger.exception("AI 분석 배치 중 오류 발생")


def start_scheduler() -> None:
    if scheduler.running:
        return

    # 매일 오전 8시 (KST) 실행
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
    scheduler.start()
    logger.info("크롤링 스케줄러 시작: 매일 오전 8시 (KST)")


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)  # ✅ 종료 시 hang 방지
        logger.info("크롤링 스케줄러 종료")