from datetime import datetime, time, timezone
from typing import Any, Dict, List, Tuple

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.importance_score import ImportanceScore
from app.models.keyword import Keyword
from app.schemas.importance import ImportanceListQuery


class ImportanceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_importance_list(
        self,
        user_id: int,
        query: ImportanceListQuery,
    ) -> Tuple[List[Dict[str, Any]], int]:
        matched_keyword_subq = (
            select(
                ArticleMatch.article_id.label("article_id"),
                func.min(ArticleMatch.keyword_id).label("keyword_id"),
            )
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(Keyword.user_id == user_id)
            .group_by(ArticleMatch.article_id)
            .subquery()
        )

        stmt = (
            select(
                ImportanceScore.article_id,
                Article.title,
                Article.url,
                matched_keyword_subq.c.keyword_id,
                ImportanceScore.score,
                ImportanceScore.status,
                ImportanceScore.created_at.label("scored_at"),
                ImportanceScore.created_at,
            )
            .join(Article, Article.id == ImportanceScore.article_id)
            .outerjoin(
                matched_keyword_subq,
                matched_keyword_subq.c.article_id == ImportanceScore.article_id,
            )
            .where(ImportanceScore.user_id == user_id)
            .where(ImportanceScore.is_current.is_(True))
        )

        if query.keyword_id:
            stmt = stmt.where(
                ImportanceScore.article_id.in_(
                    select(ArticleMatch.article_id)
                    .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
                    .where(
                        ArticleMatch.keyword_id == query.keyword_id,
                        Keyword.user_id == user_id,
                    )
                )
            )

        if query.from_date:
            stmt = stmt.where(
                Article.published_at >= datetime.combine(query.from_date, time.min)
            )

        if query.to_date:
            stmt = stmt.where(
                Article.published_at <= datetime.combine(query.to_date, time.max)
            )

        if query.min_score is not None:
            stmt = stmt.where(ImportanceScore.score >= query.min_score)

        if query.max_score is not None:
            stmt = stmt.where(ImportanceScore.score <= query.max_score)

        if query.status:
            stmt = stmt.where(ImportanceScore.status == query.status.value)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt)
        total = total or 0

        sort_map = {
            "scored_at_desc": ImportanceScore.created_at.desc().nullslast(),
            "scored_at_asc": ImportanceScore.created_at.asc().nullsfirst(),
            "score_desc": ImportanceScore.score.desc().nullslast(),
            "score_asc": ImportanceScore.score.asc().nullsfirst(),
        }

        stmt = stmt.order_by(sort_map[query.sort.value], ImportanceScore.id.desc())
        stmt = stmt.offset((query.page - 1) * query.size).limit(query.size)

        result = await self.db.execute(stmt)
        rows = result.mappings().all()
        return [dict(row) for row in rows], total
    async def clear_current_scores(self, user_id: int, article_ids: list[int]) -> None:
        if not article_ids:
            return

        stmt = (
            update(ImportanceScore)
            .where(ImportanceScore.user_id == user_id)
            .where(ImportanceScore.article_id.in_(article_ids))
            .where(ImportanceScore.is_current.is_(True))
            .values(is_current=False)
        )
        await self.db.execute(stmt)

    async def bulk_insert_scores(
        self,
        user_id: int,
        items: list[dict],
        engine: str = "gpt-4o-mini",
        version: int = 1,
    ) -> None:
        now = datetime.now(timezone.utc)

        for item in items:
            self.db.add(
                ImportanceScore(
                    article_id=item["article_id"],
                    user_id=user_id,
                    score=item["score"],
                    reason=item.get("reason"),
                    status="COMPLETED",
                    scored_at=now,
                    engine=engine,
                    version=version,
                    is_current=True,
                )
            )

        await self.db.flush()
        
        
    async def get_current_score(
        self,
        user_id: int,
        article_id: int,
    ) -> dict[str, Any] | None:
        stmt = (
            select(
                ImportanceScore.article_id,
                ImportanceScore.score,
                ImportanceScore.reason,
                ImportanceScore.status,
                ImportanceScore.scored_at,
                ImportanceScore.engine,
                ImportanceScore.version,
            )
            .where(ImportanceScore.user_id == user_id)
            .where(ImportanceScore.article_id == article_id)
            .where(ImportanceScore.is_current.is_(True))
            .order_by(ImportanceScore.id.desc())
            .limit(1)
        )

        result = await self.db.execute(stmt)
        row = result.mappings().first()
        return dict(row) if row else None

    async def save_user_score(
        self,
        user_id: int,
        article_id: int,
        score: float,
        reason: str | None,
    ) -> ImportanceScore:
        now = datetime.now(timezone.utc)

        await self.db.execute(
            update(ImportanceScore)
            .where(ImportanceScore.user_id == user_id)
            .where(ImportanceScore.article_id == article_id)
            .where(ImportanceScore.is_current.is_(True))
            .values(is_current=False)
        )

        row = ImportanceScore(
            article_id=article_id,
            user_id=user_id,
            score=score,
            reason=reason,
            status="COMPLETED",
            scored_at=now,
            engine="user",
            version=1,
            is_current=True,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def get_paired_scores(self, user_id: int) -> list[dict[str, Any]]:
        """Return rows where the user has both a manual score and a prior AI score."""
        user_scores_stmt = (
            select(ImportanceScore.article_id, ImportanceScore.score.label("user_score"))
            .where(ImportanceScore.user_id == user_id)
            .where(ImportanceScore.engine == "user")
        )
        result = await self.db.execute(user_scores_stmt)
        user_rows = result.mappings().all()

        if not user_rows:
            return []

        article_ids = [r["article_id"] for r in user_rows]

        ai_scores_stmt = (
            select(ImportanceScore.article_id, ImportanceScore.score.label("ai_score"))
            .where(ImportanceScore.user_id == user_id)
            .where(ImportanceScore.engine != "user")
            .where(ImportanceScore.article_id.in_(article_ids))
            .order_by(ImportanceScore.article_id, ImportanceScore.id.desc())
        )
        ai_result = await self.db.execute(ai_scores_stmt)
        ai_rows = ai_result.mappings().all()

        ai_by_article = {}
        for row in ai_rows:
            if row["article_id"] not in ai_by_article:
                ai_by_article[row["article_id"]] = row["ai_score"]

        pairs = []
        for row in user_rows:
            aid = row["article_id"]
            if aid in ai_by_article:
                pairs.append({
                    "article_id": aid,
                    "user_score": row["user_score"],
                    "ai_score": ai_by_article[aid],
                })

        return pairs

    async def get_user_scored_article_ids(self, user_id: int) -> set[int]:
        """Article IDs where the current score was set manually by the user."""
        result = await self.db.execute(
            select(ImportanceScore.article_id)
            .where(ImportanceScore.user_id == user_id)
            .where(ImportanceScore.engine == "user")
            .where(ImportanceScore.is_current.is_(True))
        )
        return {row[0] for row in result.all()}