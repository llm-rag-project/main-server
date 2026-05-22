from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_analysis import ArticleAnalysis
from app.models.article_match import ArticleMatch
from app.models.keyword import Keyword


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
        since = date.today() - timedelta(days=days)

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
        since = date.today() - timedelta(days=days)

        rows = await self.db.execute(
            select(
                func.date(Article.published_at).label("date"),
                func.count(func.distinct(Article.id)).label("article_count"),
            )
            .join(ArticleMatch, ArticleMatch.article_id == Article.id)
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(
                Keyword.user_id == user_id,
                Article.published_at >= since,
            )
            .group_by(func.date(Article.published_at))
            .order_by(func.date(Article.published_at))
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
        since = date.today() - timedelta(days=days)

        rows = await self.db.execute(
            select(
                Keyword.id.label("keyword_id"),
                Keyword.keyword_text,
                func.date(Article.published_at).label("date"),
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
                func.date(Article.published_at),
            )
            .order_by(
                Keyword.keyword_text,
                func.date(Article.published_at),
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
        since = date.today() - timedelta(days=days)

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
        since = date.today() - timedelta(days=days)

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
        since = date.today() - timedelta(days=days)

        rows = await self.db.execute(
            select(
                Keyword.keyword_text,
                func.date(Article.published_at).label("date"),
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
            .group_by(Keyword.keyword_text, func.date(Article.published_at), ArticleAnalysis.sentiment)
            .order_by(Keyword.keyword_text, func.date(Article.published_at))
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