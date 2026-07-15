import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from zoneinfo import ZoneInfo

from app.core.transnews_client import TransNewsClient
from app.db.session import engine
from app.api.v1.reports import (
    build_dongguk_auto_email_request,
    deliver_dongguk_email_for_scheduler,
    prebuild_dongguk_mail_drafts_for_scheduler,
)
from app.models.crawl_run import CrawlRun
from app.models.email_delivery import EmailDelivery
from app.models.keyword import Keyword
from app.models.user import User
from app.repositories.stats_repository import StatsRepository
from app.services.analysis_service import AnalysisService
from app.services.auto_ai_service import AutoAiService
from app.services.crawl_run_service import CrawlRunService
from app.services.stats_service import StatsService

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


def _unpack_recipients(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.replace(",", "\n").splitlines() if item.strip()]

scheduler = AsyncIOScheduler()
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
_daily_crawl_retry_in_progress = False


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
            prebuild_result = await prebuild_dongguk_mail_drafts_for_scheduler(db)
            logger.info("Dongguk Dify mail draft prebuild finished: %s", prebuild_result)
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


async def run_missed_daily_crawling() -> None:
    global _daily_crawl_retry_in_progress

    now_kst = datetime.now(KST)
    scheduled_at_kst = now_kst.replace(hour=8, minute=0, second=0, microsecond=0)

    if now_kst < scheduled_at_kst:
        logger.info("Daily crawl catch-up skipped: before scheduled time")
        return

    if _daily_crawl_retry_in_progress:
        logger.info("Daily crawl catch-up skipped: retry already in progress")
        return

    scheduled_at_utc = scheduled_at_kst.astimezone(timezone.utc).replace(tzinfo=None)

    try:
        async with SessionLocal() as db:
            completed_run_id = await db.scalar(
                select(CrawlRun.id)
                .where(CrawlRun.started_at >= scheduled_at_utc)
                .where(CrawlRun.status == "COMPLETED")
                .limit(1)
            )
            running_run_id = await db.scalar(
                select(CrawlRun.id)
                .where(CrawlRun.started_at >= scheduled_at_utc)
                .where(CrawlRun.status == "RUNNING")
                .limit(1)
            )
    except Exception:
        logger.exception("Daily crawl catch-up check failed")
        return

    if completed_run_id:
        logger.info("Daily crawl catch-up skipped: already completed today run_id=%s", completed_run_id)
        return

    if running_run_id:
        logger.info("Daily crawl catch-up skipped: crawl already running run_id=%s", running_run_id)
        return

    _daily_crawl_retry_in_progress = True
    try:
        logger.info("Daily crawl catch-up retry started: no completed 08:00 KST crawl yet")
        await run_periodic_crawling()
    finally:
        _daily_crawl_retry_in_progress = False


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


async def run_dongguk_auto_email() -> None:
    now = datetime.now(KST)
    send_time = now.strftime("%H:%M")
    mail_date = now.date().isoformat()
    logger.info("Dongguk PR auto email check started: %s", send_time)
    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(Keyword, User)
                .join(User, User.id == Keyword.user_id)
                .where(Keyword.is_active.is_(True))
                .where(Keyword.email_auto_send.is_(True))
            )
            rows = result.all()
            sent_count = 0
            skipped_count = 0

            for keyword, user in rows:
                configured_send_time = (keyword.email_send_time or "08:30")[:5]
                if send_time < configured_send_time:
                    skipped_count += 1
                    logger.info(
                        "Dongguk PR auto email skipped: before configured time keyword_id=%s configured=%s now=%s",
                        keyword.id,
                        configured_send_time,
                        send_time,
                    )
                    continue

                recipients = _unpack_recipients(keyword.email_recipients)
                if not recipients:
                    skipped_count += 1
                    logger.info("Dongguk PR auto email skipped: no recipients keyword_id=%s", keyword.id)
                    continue

                body = await build_dongguk_auto_email_request(
                    db,
                    user_id=user.id,
                    keyword_id=keyword.id,
                    to_emails=recipients,
                    mail_date=mail_date,
                )
                if body is None:
                    skipped_count += 1
                    logger.info("Dongguk PR auto email skipped: no articles keyword_id=%s mail_date=%s", keyword.id, mail_date)
                    continue

                existing = await db.scalar(
                    select(EmailDelivery.id)
                    .where(EmailDelivery.user_id == user.id)
                    .where(EmailDelivery.subject == body.subject)
                    .where(EmailDelivery.status == "SENT")
                    .limit(1)
                )
                if existing:
                    skipped_count += 1
                    logger.info("Dongguk PR auto email skipped: already sent keyword_id=%s subject=%s", keyword.id, body.subject)
                    continue

                result_data = await deliver_dongguk_email_for_scheduler(
                    db=db,
                    current_user=user,
                    body=body,
                )
                if result_data.get("article_count"):
                    sent_count += 1
                else:
                    skipped_count += 1

            logger.info("Dongguk PR auto email check finished: sent=%s skipped=%s", sent_count, skipped_count)
    except Exception:
        logger.exception("Dongguk PR auto email failed")

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
        run_missed_daily_crawling,
        trigger="date",
        run_date=datetime.now(KST) + timedelta(seconds=20),
        timezone="Asia/Seoul",
        id="daily-crawl-startup-catchup-job",
        replace_existing=True,
        misfire_grace_time=120,
        max_instances=1,
    )
    scheduler.add_job(
        run_missed_daily_crawling,
        trigger="cron",
        minute="*/10",
        timezone="Asia/Seoul",
        id="daily-crawl-safety-catchup-job",
        replace_existing=True,
        misfire_grace_time=120,
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
    scheduler.add_job(
        run_dongguk_auto_email,
        trigger="cron",
        minute="*",
        timezone="Asia/Seoul",
        id="dongguk-pr-auto-email-job",
        replace_existing=True,
        misfire_grace_time=120,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started: daily crawl at 08:00 KST, hourly news search metrics, Dongguk PR auto email")


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

