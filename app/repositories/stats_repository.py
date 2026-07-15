from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_analysis import ArticleAnalysis
from app.models.article_match import ArticleMatch
from app.models.keyword import Keyword
from app.models.news_search_metric import NewsSearchMetric
from app.models.social_metric import SocialMetric


KST = ZoneInfo("Asia/Seoul")


def _kst_day_start(days: int) -> datetime:
    today = datetime.now(KST).date()
    return datetime.combine(today - timedelta(days=days), datetime.min.time(), tzinfo=KST)


def _kst_date(column):
    return func.date(func.timezone("Asia/Seoul", column))


class StatsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_keywords(self, user_id: int) -> list[Keyword]:
        rows = await self.db.execute(
            select(Keyword).where(
                Keyword.user_id == user_id,
                Keyword.is_active.is_(True),
            )
        )
        return list(rows.scalars().all())

    async def get_article_count_by_keyword(
        self, user_id: int, days: int = 7
    ) -> list[dict]:
        """키워드별 기사 수 (최근 N일)"""
        since = _kst_day_start(days)

        rows = await self.db.execute(
            select(
                Keyword.id.label("keyword_id"),
                Keyword.keyword_text,
                func.count(ArticleMatch.article_id).label("article_count"),
            )
            .join(ArticleMatch, ArticleMatch.keyword_id == Keyword.id)
            .join(Article, Article.id == ArticleMatch.article_id)
            .where(
                Keyword.user_id == user_id,
                Keyword.is_active.is_(True),
                Article.published_at >= since,
            )
            .group_by(Keyword.id, Keyword.keyword_text)
            .order_by(func.count(ArticleMatch.article_id).desc())
        )
        return [
            {
                "keyword_id": r.keyword_id,
                "keyword_text": r.keyword_text,
                "article_count": r.article_count,
            }
            for r in rows.all()
        ]

    async def get_article_count_by_date(
        self, user_id: int, days: int = 7
    ) -> list[dict]:
        """날짜별 수집 기사 수 (최근 N일, 날짜 오름차순)"""
        since = _kst_day_start(days)
        published_date = _kst_date(Article.published_at)

        rows = await self.db.execute(
            select(
                published_date.label("date"),
                func.count(func.distinct(Article.id)).label("article_count"),
            )
            .join(ArticleMatch, ArticleMatch.article_id == Article.id)
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(
                Keyword.user_id == user_id,
                Article.published_at >= since,
            )
            .group_by(published_date)
            .order_by(published_date)
        )
        return [
            {
                "date": str(r.date),
                "article_count": r.article_count,
            }
            for r in rows.all()
        ]

    async def get_article_count_by_date_per_keyword(
        self, user_id: int, days: int = 7
    ) -> list[dict]:
        """키워드 × 날짜별 기사 수 (그래프 비교용)"""
        since = _kst_day_start(days)
        published_date = _kst_date(Article.published_at)

        rows = await self.db.execute(
            select(
                Keyword.id.label("keyword_id"),
                Keyword.keyword_text,
                published_date.label("date"),
                func.count(Article.id).label("article_count"),
            )
            .join(ArticleMatch, ArticleMatch.keyword_id == Keyword.id)
            .join(Article, Article.id == ArticleMatch.article_id)
            .where(
                Keyword.user_id == user_id,
                Keyword.is_active.is_(True),
                Article.published_at >= since,
            )
            .group_by(
                Keyword.id,
                Keyword.keyword_text,
                published_date,
            )
            .order_by(
                Keyword.keyword_text,
                published_date,
            )
        )
        return [
            {
                "keyword_id": r.keyword_id,
                "keyword_text": r.keyword_text,
                "date": str(r.date),
                "article_count": r.article_count,
            }
            for r in rows.all()
        ]

    async def get_sentiment_by_keyword(
        self, user_id: int, days: int = 7
    ) -> list[dict]:
        """키워드별 감성 분포 (긍정/부정/중립/분석실패/미분석)"""
        since = _kst_day_start(days)

        rows = await self.db.execute(
            select(
                Keyword.keyword_text,
                ArticleAnalysis.sentiment,
                func.count(Article.id).label("count"),
            )
            .join(ArticleMatch, ArticleMatch.keyword_id == Keyword.id)
            .join(Article, Article.id == ArticleMatch.article_id)
            .outerjoin(ArticleAnalysis, ArticleAnalysis.article_id == Article.id)
            .where(
                Keyword.user_id == user_id,
                Keyword.is_active.is_(True),
                Article.published_at >= since,
            )
            .group_by(Keyword.keyword_text, ArticleAnalysis.sentiment)
            .order_by(Keyword.keyword_text)
        )
        return [
            {
                "keyword_text": r.keyword_text,
                "sentiment": r.sentiment or "미분석",
                "count": r.count,
            }
            for r in rows.all()
        ]

    async def get_promotion_by_keyword(
        self, user_id: int, days: int = 7
    ) -> list[dict]:
        """키워드별 광고성 기사 비율 (광고성/일반/미분석)"""
        since = _kst_day_start(days)

        rows = await self.db.execute(
            select(
                Keyword.keyword_text,
                ArticleAnalysis.is_promotion,
                func.count(Article.id).label("count"),
            )
            .join(ArticleMatch, ArticleMatch.keyword_id == Keyword.id)
            .join(Article, Article.id == ArticleMatch.article_id)
            .outerjoin(ArticleAnalysis, ArticleAnalysis.article_id == Article.id)
            .where(
                Keyword.user_id == user_id,
                Keyword.is_active.is_(True),
                Article.published_at >= since,
            )
            .group_by(Keyword.keyword_text, ArticleAnalysis.is_promotion)
            .order_by(Keyword.keyword_text)
        )
        def _label(val):
            if val is True:
                return "📢 광고성"
            if val is False:
                return "✅ 일반"
            return "❓ 미분석"

        return [
            {
                "keyword_text": r.keyword_text,
                "promotion": _label(r.is_promotion),
                "count": r.count,
            }
            for r in rows.all()
        ]

    async def get_sentiment_by_date(
        self, user_id: int, days: int = 7
    ) -> list[dict]:
        """키워드 × 날짜별 감성 추이 (긍정/부정/중립)"""
        since = _kst_day_start(days)
        published_date = _kst_date(Article.published_at)

        rows = await self.db.execute(
            select(
                Keyword.keyword_text,
                published_date.label("date"),
                ArticleAnalysis.sentiment,
                func.count(func.distinct(Article.id)).label("count"),
            )
            .join(ArticleMatch, ArticleMatch.article_id == Article.id)
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.id)
            .where(
                Keyword.user_id == user_id,
                Keyword.is_active.is_(True),
                Article.published_at >= since,
                ArticleAnalysis.sentiment.in_(["긍정", "부정", "중립"]),
            )
            .group_by(Keyword.keyword_text, published_date, ArticleAnalysis.sentiment)
            .order_by(Keyword.keyword_text, published_date)
        )
        return [
            {
                "keyword_text": r.keyword_text,
                "date": str(r.date),
                "sentiment": r.sentiment,
                "count": r.count,
            }
            for r in rows.all()
        ]

    async def get_article_count_by_collected_date(
        self, user_id: int, days: int = 7
    ) -> list[dict]:
        since = _kst_day_start(days)
        collected_date = _kst_date(Article.created_at)

        rows = await self.db.execute(
            select(
                collected_date.label("date"),
                func.count(func.distinct(Article.id)).label("article_count"),
            )
            .join(ArticleMatch, ArticleMatch.article_id == Article.id)
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(
                Keyword.user_id == user_id,
                Article.created_at >= since,
            )
            .group_by(collected_date)
            .order_by(collected_date)
        )
        return [
            {
                "date": str(r.date),
                "article_count": r.article_count,
            }
            for r in rows.all()
        ]

    async def get_article_count_by_collected_date_per_keyword(
        self, user_id: int, days: int = 7
    ) -> list[dict]:
        since = _kst_day_start(days)
        collected_date = _kst_date(Article.created_at)

        rows = await self.db.execute(
            select(
                Keyword.id.label("keyword_id"),
                Keyword.keyword_text,
                collected_date.label("date"),
                func.count(Article.id).label("article_count"),
            )
            .join(ArticleMatch, ArticleMatch.keyword_id == Keyword.id)
            .join(Article, Article.id == ArticleMatch.article_id)
            .where(
                Keyword.user_id == user_id,
                Keyword.is_active.is_(True),
                Article.created_at >= since,
            )
            .group_by(
                Keyword.id,
                Keyword.keyword_text,
                collected_date,
            )
            .order_by(
                Keyword.keyword_text,
                collected_date,
            )
        )
        return [
            {
                "keyword_id": r.keyword_id,
                "keyword_text": r.keyword_text,
                "date": str(r.date),
                "article_count": r.article_count,
            }
            for r in rows.all()
        ]

    async def get_article_count_by_published_hour(
        self,
        user_id: int,
        *,
        target_date: date,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        keyword_id: int | None = None,
    ) -> list[dict]:
        start_at = from_at.astimezone(KST) if from_at else datetime.combine(target_date, time.min, tzinfo=KST)
        end_at = to_at.astimezone(KST) if to_at else datetime.combine(target_date, time.max, tzinfo=KST)
        published_hour = func.date_trunc("hour", func.timezone("Asia/Seoul", Article.published_at))

        stmt = (
            select(
                published_hour.label("hour"),
                func.count(func.distinct(Article.id)).label("article_count"),
            )
            .join(ArticleMatch, ArticleMatch.article_id == Article.id)
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(
                Keyword.user_id == user_id,
                Keyword.is_active.is_(True),
                Article.published_at >= start_at,
                Article.published_at <= end_at,
            )
            .group_by(published_hour)
            .order_by(published_hour)
        )
        if keyword_id:
            stmt = stmt.where(Keyword.id == keyword_id)

        rows = await self.db.execute(stmt)
        counts_by_hour = {
            r.hour.strftime("%Y-%m-%d %H:00"): int(r.article_count or 0)
            for r in rows.all()
            if r.hour
        }
        bucket_start = start_at.replace(minute=0, second=0, microsecond=0)
        hour_count = max(1, int((end_at - bucket_start).total_seconds() // 3600) + 1)
        return [
            {
                "hour": (bucket_start + timedelta(hours=hour)).strftime("%Y-%m-%d %H:00"),
                "article_count": counts_by_hour.get((bucket_start + timedelta(hours=hour)).strftime("%Y-%m-%d %H:00"), 0),
            }
            for hour in range(hour_count)
        ]

    async def get_latest_social_metrics(self, user_id: int) -> list[dict]:
        latest_subq = (
            select(
                SocialMetric.keyword_id,
                SocialMetric.source,
                func.max(SocialMetric.sampled_at).label("sampled_at"),
            )
            .where(SocialMetric.user_id == user_id)
            .group_by(SocialMetric.keyword_id, SocialMetric.source)
            .subquery()
        )

        rows = await self.db.execute(
            select(
                SocialMetric.keyword_id,
                SocialMetric.keyword_text,
                SocialMetric.source,
                SocialMetric.mention_count,
                SocialMetric.positive_hint_count,
                SocialMetric.negative_hint_count,
                SocialMetric.sampled_at,
            )
            .join(
                latest_subq,
                (latest_subq.c.keyword_id == SocialMetric.keyword_id)
                & (latest_subq.c.source == SocialMetric.source)
                & (latest_subq.c.sampled_at == SocialMetric.sampled_at),
            )
            .where(SocialMetric.user_id == user_id)
        )

        return [
            {
                "keyword_id": r.keyword_id,
                "keyword_text": r.keyword_text,
                "source": r.source,
                "mention_count": r.mention_count,
                "positive_hint_count": r.positive_hint_count,
                "negative_hint_count": r.negative_hint_count,
                "sampled_at": r.sampled_at.isoformat() if r.sampled_at else None,
            }
            for r in rows.all()
        ]

    async def get_social_metrics_by_sampled_date(
        self,
        user_id: int,
        *,
        target_date: date,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        keyword_id: int | None = None,
    ) -> list[dict]:
        end_at = to_at.astimezone(KST) if to_at else datetime.combine(target_date, time.max, tzinfo=KST)
        start_at = from_at.astimezone(KST) if from_at else end_at - timedelta(minutes=5)
        latest_subq = (
            select(
                SocialMetric.keyword_id,
                SocialMetric.source,
                func.max(SocialMetric.sampled_at).label("sampled_at"),
            )
            .where(
                SocialMetric.user_id == user_id,
                SocialMetric.sampled_at >= start_at,
                SocialMetric.sampled_at <= end_at,
            )
            .group_by(SocialMetric.keyword_id, SocialMetric.source)
            .subquery()
        )

        stmt = (
            select(
                SocialMetric.keyword_id,
                SocialMetric.keyword_text,
                SocialMetric.source,
                SocialMetric.mention_count,
                SocialMetric.positive_hint_count,
                SocialMetric.negative_hint_count,
                SocialMetric.sampled_at,
            )
            .join(
                latest_subq,
                (latest_subq.c.keyword_id == SocialMetric.keyword_id)
                & (latest_subq.c.source == SocialMetric.source)
                & (latest_subq.c.sampled_at == SocialMetric.sampled_at),
            )
            .where(SocialMetric.user_id == user_id)
        )
        if keyword_id:
            stmt = stmt.where(SocialMetric.keyword_id == keyword_id)

        rows = await self.db.execute(stmt)
        return [
            {
                "keyword_id": r.keyword_id,
                "keyword_text": r.keyword_text,
                "source": r.source,
                "mention_count": r.mention_count,
                "positive_hint_count": r.positive_hint_count,
                "negative_hint_count": r.negative_hint_count,
                "sampled_at": r.sampled_at.isoformat() if r.sampled_at else None,
            }
            for r in rows.all()
        ]

    async def add_social_metric(
        self,
        *,
        user_id: int,
        keyword_id: int,
        keyword_text: str,
        source: str,
        mention_count: int,
        positive_hint_count: int = 0,
        negative_hint_count: int = 0,
        sampled_at: datetime | None = None,
    ) -> SocialMetric:
        metric = SocialMetric(
            user_id=user_id,
            keyword_id=keyword_id,
            keyword_text=keyword_text,
            source=source,
            mention_count=mention_count,
            positive_hint_count=positive_hint_count,
            negative_hint_count=negative_hint_count,
            sampled_at=sampled_at,
        )
        self.db.add(metric)
        await self.db.flush()
        return metric

    async def add_news_search_metric(
        self,
        *,
        user_id: int,
        keyword_id: int,
        keyword_text: str,
        total_count: int,
        min_count: int = 0,
        max_count: int = 0,
        sampled_at: datetime | None = None,
    ) -> NewsSearchMetric:
        metric = NewsSearchMetric(
            user_id=user_id,
            keyword_id=keyword_id,
            keyword_text=keyword_text,
            total_count=total_count,
            min_count=min_count,
            max_count=max_count,
            sampled_at=sampled_at or datetime.now(timezone.utc),
        )
        self.db.add(metric)
        await self.db.flush()
        await self.db.refresh(metric)
        return metric

    async def get_latest_news_search_metrics(self, user_id: int) -> list[dict]:
        latest_subq = (
            select(
                NewsSearchMetric.keyword_id,
                func.max(NewsSearchMetric.sampled_at).label("sampled_at"),
            )
            .where(NewsSearchMetric.user_id == user_id)
            .where(NewsSearchMetric.min_count == 0)
            .group_by(NewsSearchMetric.keyword_id)
            .subquery()
        )

        rows = await self.db.execute(
            select(
                NewsSearchMetric.keyword_id,
                NewsSearchMetric.keyword_text,
                NewsSearchMetric.total_count,
                NewsSearchMetric.min_count,
                NewsSearchMetric.max_count,
                NewsSearchMetric.sampled_at,
            )
            .join(
                latest_subq,
                (latest_subq.c.keyword_id == NewsSearchMetric.keyword_id)
                & (latest_subq.c.sampled_at == NewsSearchMetric.sampled_at),
            )
            .where(NewsSearchMetric.user_id == user_id)
            .where(NewsSearchMetric.min_count == 0)
        )

        return [
            {
                "keyword_id": r.keyword_id,
                "keyword_text": r.keyword_text,
                "total_count": r.total_count,
                "min_count": r.min_count,
                "max_count": r.max_count,
                "sampled_at": r.sampled_at.isoformat() if r.sampled_at else None,
            }
            for r in rows.all()
        ]

    async def get_news_search_metric_trend(self, user_id: int, hours: int = 48) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = await self.db.execute(
            select(
                NewsSearchMetric.keyword_id,
                NewsSearchMetric.keyword_text,
                NewsSearchMetric.total_count,
                NewsSearchMetric.min_count,
                NewsSearchMetric.max_count,
                NewsSearchMetric.sampled_at,
            )
            .where(
                NewsSearchMetric.user_id == user_id,
                NewsSearchMetric.sampled_at >= since,
                NewsSearchMetric.min_count == 0,
            )
            .order_by(NewsSearchMetric.keyword_text, NewsSearchMetric.sampled_at)
        )

        return [
            {
                "keyword_id": r.keyword_id,
                "keyword_text": r.keyword_text,
                "total_count": r.total_count,
                "min_count": r.min_count,
                "max_count": r.max_count,
                "sampled_at": r.sampled_at.isoformat() if r.sampled_at else None,
            }
            for r in rows.all()
        ]
