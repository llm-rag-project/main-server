import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from zoneinfo import ZoneInfo

from app.core.transnews_client import TransNewsClient
from app.db.session import engine
from app.api.v1.reports import (
    _dongguk_mail_subject,
    build_dongguk_auto_email_request,
    deliver_dongguk_email_for_scheduler,
    prebuild_dongguk_mail_drafts_for_scheduler,
)
from app.models.crawl_run import CrawlRun
from app.models.crawl_run_keyword import CrawlRunKeyword
from app.models.crawl_run_source import CrawlRunSource
from app.models.email_delivery import EmailDelivery
from app.models.keyword import Keyword
from app.models.user import User
from app.repositories.stats_repository import StatsRepository
from app.services.analysis_service import AnalysisService
from app.services.auto_ai_service import AutoAiService
from app.services.crawl_run_service import CrawlRunService
from app.services.stats_service import StatsService
from app.services.holiday_service import HolidayService
from app.services.priority_insight_service import (
    PriorityInsightService,
    previous_month_period,
    previous_quarter_period,
)

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


def _unpack_recipients(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.replace(",", "\n").splitlines() if item.strip()]

scheduler = AsyncIOScheduler()
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
_daily_crawl_retry_in_progress = False
_dongguk_refresh_in_progress = False
AUTO_RETRY_MAX_ATTEMPTS = 3
AUTO_RETRY_SECTION_POOL_TARGET_COUNT = 10
AUTO_RETRY_TRIGGER_TYPES = ("daily_refresh", "auto_retry")
DAILY_COLLECTION_TRIGGER_TYPES = ("scheduled", "daily_refresh", "auto_retry")
CORE_COLLECTION_SOURCES = {
    "dongguk_official",
    "google_rss",
    "media_direct_pool",
    "media_site_direct",
    "naver",
    "relation_expansion",
}
REQUIRED_COLLECTION_GROUPS = (
    CORE_COLLECTION_SOURCES,
    {"section_pool_education"},
    {"section_pool_buddhism"},
)


def _source_has_usable_result(source: CrawlRunSource) -> bool:
    if source.source_name in {"section_pool_education", "section_pool_buddhism"}:
        # Section discovery can include candidates outside the requested mail
        # window. Only a stored or already-linked article proves that the
        # category is represented in the target window.
        return (
            int(source.stored_count or 0) > 0
            or int(source.duplicate_count or 0) > 0
        )
    return (
        int(source.discovered_count or 0) > 0
        or int(source.stored_count or 0) > 0
        or int(source.duplicate_count or 0) > 0
    )


def _dongguk_collection_needs_retry(sources: list[CrawlRunSource]) -> bool:
    if not sources:
        return True

    return any(
        not any(
            source.source_name in group and _source_has_usable_result(source)
            for source in sources
        )
        for group in REQUIRED_COLLECTION_GROUPS
    )


async def _dongguk_retry_state(
    db,
    *,
    keyword_id: int,
    scheduled_at_utc: datetime,
) -> dict:
    crawl_run_cutoff = scheduled_at_utc.replace(tzinfo=None)
    running_run_id = await db.scalar(
        select(CrawlRun.id)
        .join(CrawlRunKeyword, CrawlRunKeyword.crawl_run_id == CrawlRun.id)
        .where(CrawlRunKeyword.keyword_id == keyword_id)
        .where(CrawlRun.started_at >= crawl_run_cutoff)
        .where(CrawlRun.status == "RUNNING")
        .limit(1)
    )

    attempt_count = int(
        await db.scalar(
            select(func.count(func.distinct(CrawlRunSource.crawl_run_id)))
            .where(CrawlRunSource.keyword_id == keyword_id)
            .where(CrawlRunSource.created_at >= scheduled_at_utc)
            .where(CrawlRunSource.trigger_type.in_(AUTO_RETRY_TRIGGER_TYPES))
        )
        or 0
    )

    latest_run_id = await db.scalar(
        select(CrawlRunSource.crawl_run_id)
        .where(CrawlRunSource.keyword_id == keyword_id)
        .where(CrawlRunSource.created_at >= scheduled_at_utc)
        .where(CrawlRunSource.trigger_type.in_(DAILY_COLLECTION_TRIGGER_TYPES))
        .order_by(CrawlRunSource.created_at.desc(), CrawlRunSource.id.desc())
        .limit(1)
    )

    sources: list[CrawlRunSource] = []
    if latest_run_id:
        sources = list(
            (
                await db.scalars(
                    select(CrawlRunSource)
                    .where(CrawlRunSource.crawl_run_id == latest_run_id)
                    .where(CrawlRunSource.keyword_id == keyword_id)
                )
            ).all()
        )

    return {
        "running_run_id": running_run_id,
        "attempt_count": attempt_count,
        "latest_run_id": latest_run_id,
        "needs_retry": _dongguk_collection_needs_retry(sources),
    }


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


async def run_dongguk_daily_refresh() -> None:
    """Retry incomplete Dongguk collection runs up to three times per day."""
    global _dongguk_refresh_in_progress

    if _dongguk_refresh_in_progress:
        logger.info("Dongguk daily refresh skipped: refresh already in progress")
        return

    _dongguk_refresh_in_progress = True
    try:
        async with SessionLocal() as db:
            now_kst = datetime.now(KST)
            scheduled_at_utc = now_kst.replace(
                hour=8,
                minute=0,
                second=0,
                microsecond=0,
            ).astimezone(timezone.utc)
            rows = (
                await db.execute(
                    select(Keyword.user_id, Keyword.id)
                    .where(Keyword.is_active.is_(True))
                    .where(Keyword.dashboard_mode == "dongguk")
                    .order_by(Keyword.user_id, Keyword.id)
                )
            ).all()
            keyword_ids_by_user: dict[int, list[int]] = {}
            for user_id, keyword_id in rows:
                keyword_ids_by_user.setdefault(int(user_id), []).append(int(keyword_id))

            service = CrawlRunService(db=db, transnews_client=TransNewsClient())
            refresh_runs: list[dict] = []
            for user_id, keyword_ids in keyword_ids_by_user.items():
                retry_keyword_ids: list[int] = []
                for keyword_id in keyword_ids:
                    state = await _dongguk_retry_state(
                        db,
                        keyword_id=keyword_id,
                        scheduled_at_utc=scheduled_at_utc,
                    )
                    if state["running_run_id"]:
                        logger.info(
                            "Dongguk auto retry skipped: keyword_id=%s run_id=%s still running",
                            keyword_id,
                            state["running_run_id"],
                        )
                        continue
                    if state["attempt_count"] >= AUTO_RETRY_MAX_ATTEMPTS:
                        logger.info(
                            "Dongguk auto retry limit reached: keyword_id=%s attempts=%s",
                            keyword_id,
                            state["attempt_count"],
                        )
                        continue
                    if state["latest_run_id"] and not state["needs_retry"]:
                        logger.info(
                            "Dongguk auto retry skipped: keyword_id=%s latest run is healthy",
                            keyword_id,
                        )
                        continue
                    retry_keyword_ids.append(keyword_id)

                if not retry_keyword_ids:
                    continue

                try:
                    run_result = await service.create_crawl_run(
                        user_id=user_id,
                        keyword_ids=retry_keyword_ids,
                        force=True,
                        today_only=True,
                        discovery_only=True,
                        enrich_for_relevance=True,
                        trigger_type="auto_retry",
                        section_pool_target_count=AUTO_RETRY_SECTION_POOL_TARGET_COUNT,
                        search_sort="latest",
                    )
                    refresh_runs.append(
                        {
                            "user_id": user_id,
                            "keyword_ids": retry_keyword_ids,
                            **run_result,
                        }
                    )
                    if run_result.get("crawl_run_id"):
                        await AutoAiService(db).run_for_crawl_run(
                            user_id=user_id,
                            crawl_run_id=run_result["crawl_run_id"],
                        )
                except Exception:
                    logger.exception(
                        "Dongguk auto retry failed: user_id=%s keyword_ids=%s",
                        user_id,
                        retry_keyword_ids,
                    )

            if refresh_runs:
                prebuild_result = await prebuild_dongguk_mail_drafts_for_scheduler(db)
                logger.info(
                    "Dongguk auto retry completed: runs=%s prebuild=%s",
                    refresh_runs,
                    prebuild_result,
                )
            else:
                logger.info("Dongguk auto retry skipped: all active keywords are healthy or exhausted")
    finally:
        _dongguk_refresh_in_progress = False


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
                work_window = await HolidayService(db).work_window(user.id, now.date())
                if not work_window["is_target_business_day"]:
                    skipped_count += 1
                    logger.info(
                        "Dongguk PR auto email skipped: non-business day keyword_id=%s date=%s",
                        keyword.id,
                        mail_date,
                    )
                    continue

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

                subject = _dongguk_mail_subject(mail_date)
                existing = await db.scalar(
                    select(EmailDelivery.id)
                    .where(EmailDelivery.user_id == user.id)
                    .where(EmailDelivery.subject == subject)
                    .where(EmailDelivery.status == "SENT")
                    .limit(1)
                )
                if existing:
                    skipped_count += 1
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


async def run_priority_insight_cycle() -> None:
    """Create missing monthly insight and latest completed-quarter recalibration."""
    today = datetime.now(KST).date()
    month_start, month_end, month_key = previous_month_period(today)
    quarter_period = previous_quarter_period(today)
    logger.info("Dongguk priority insight cycle started: monthly=%s", month_key)
    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(Keyword)
                .where(
                    Keyword.is_active.is_(True),
                    Keyword.dashboard_mode == "dongguk",
                )
            )
            keywords = list(result.scalars().all())
            generated = 0
            failed = 0
            for keyword in keywords:
                service = PriorityInsightService(db)
                try:
                    await service.generate_insight(
                        user_id=keyword.user_id,
                        keyword_id=keyword.id,
                        period_start=month_start,
                        period_end=month_end,
                        period_key=month_key,
                        cadence="monthly",
                    )
                    if quarter_period:
                        quarter_start, quarter_end, quarter_key = quarter_period
                        await service.generate_insight(
                            user_id=keyword.user_id,
                            keyword_id=keyword.id,
                            period_start=quarter_start,
                            period_end=quarter_end,
                            period_key=quarter_key,
                            cadence="quarterly",
                        )
                    generated += 1
                except Exception:
                    failed += 1
                    logger.exception("Priority insight generation failed keyword_id=%s", keyword.id)
            logger.info(
                "Dongguk priority insight cycle finished: keywords=%s generated=%s failed=%s",
                len(keywords),
                generated,
                failed,
            )
    except Exception:
        logger.exception("Dongguk priority insight cycle failed")

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
        run_dongguk_daily_refresh,
        trigger="cron",
        hour="8-18",
        minute="15,45",
        timezone="Asia/Seoul",
        id="dongguk-auto-retry-job",
        replace_existing=True,
        misfire_grace_time=300,
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
    scheduler.add_job(
        run_priority_insight_cycle,
        trigger="cron",
        hour=7,
        minute=10,
        timezone="Asia/Seoul",
        id="dongguk-priority-insight-cycle-job",
        replace_existing=True,
        misfire_grace_time=3600,
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "Scheduler started: daily crawl at 08:00 KST, Dongguk auto retry every 30 minutes "
        "(08:15-18:45, max 3 attempts), "
        "hourly news search metrics, "
        "Dongguk PR auto email, priority insight cycle at 07:10 KST"
    )


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

