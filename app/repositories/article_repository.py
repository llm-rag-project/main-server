from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, exists, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete
from app.models.feedback import Feedback

from app.models.feedback import Feedback
from app.models.importance_score import ImportanceScore
from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.feedback import Feedback
from app.models.importance_score import ImportanceScore
from app.models.keyword import Keyword
from app.models.summary import Summary
from app.schemas.articles import ArticleListQuery


class ArticleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_article_list(
        self,
        user_id: int,
        query: ArticleListQuery,
    ) -> Tuple[List[Dict[str, Any]], int]:
        latest_summary_subq = (
            select(
                Summary.article_id.label("article_id"),
                Summary.summary_text.label("summary_text"),
                Summary.language.label("summary_language"),
                func.row_number()
                .over(
                    partition_by=Summary.article_id,
                    order_by=Summary.created_at.desc(),
                )
                .label("rn"),
            )
            .subquery()
        )

        latest_importance_subq = (
            select(
                ImportanceScore.article_id.label("article_id"),
                ImportanceScore.user_id.label("user_id"),
                ImportanceScore.score.label("score"),
                ImportanceScore.status.label("status"),
                ImportanceScore.created_at.label("scored_at"),
                func.row_number()
                .over(
                    partition_by=(ImportanceScore.article_id, ImportanceScore.user_id),
                    order_by=ImportanceScore.created_at.desc(),
                )
                .label("rn"),
            )
            .subquery()
        )

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

        has_feedback_expr = exists(
            select(literal(1))
            .select_from(Feedback)
            .where(
                Feedback.article_id == Article.id,
                Feedback.user_id == user_id,
            )
        )

        is_liked_expr = exists(
            select(literal(1))
            .select_from(Feedback)
            .where(
                Feedback.article_id == Article.id,
                Feedback.user_id == user_id,
                Feedback.label == "LIKE",
            )
        )

        accessible_articles_expr = exists(
            select(literal(1))
            .select_from(ArticleMatch)
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(
                ArticleMatch.article_id == Article.id,
                Keyword.user_id == user_id,
            )
        )

        stmt = (
            select(
                Article.id,
                Article.title,
                latest_summary_subq.c.summary_text.label("summary"),
                Article.url,
                Article.publisher.label("source"),
                Article.language,
                Article.published_at,
                matched_keyword_subq.c.keyword_id,
                latest_importance_subq.c.score.label("importance"),
                case((is_liked_expr, True), else_=False).label("is_liked"),
                case((has_feedback_expr, True), else_=False).label("has_feedback"),
            )
            .select_from(Article)
            .outerjoin(
                latest_summary_subq,
                and_(
                    latest_summary_subq.c.article_id == Article.id,
                    latest_summary_subq.c.rn == 1,
                ),
            )
            .outerjoin(
                latest_importance_subq,
                and_(
                    latest_importance_subq.c.article_id == Article.id,
                    latest_importance_subq.c.user_id == user_id,
                    latest_importance_subq.c.rn == 1,
                ),
            )
            .outerjoin(
                matched_keyword_subq,
                matched_keyword_subq.c.article_id == Article.id,
            )
            .where(accessible_articles_expr)
        )

        if query.keyword_id:
            stmt = stmt.where(
                exists(
                    select(literal(1))
                    .select_from(ArticleMatch)
                    .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
                    .where(
                        ArticleMatch.article_id == Article.id,
                        ArticleMatch.keyword_id == query.keyword_id,
                        Keyword.user_id == user_id,
                    )
                )
            )

        if query.q:
            like_expr = f"%{query.q.strip()}%"
            stmt = stmt.where(
                or_(
                    Article.title.ilike(like_expr),
                    Article.content.ilike(like_expr),
                    latest_summary_subq.c.summary_text.ilike(like_expr),
                )
            )

        if query.language:
            stmt = stmt.where(Article.language == query.language.value)

        if query.from_date:
            stmt = stmt.where(
                Article.published_at >= datetime.combine(query.from_date, time.min)
            )

        if query.to_date:
            stmt = stmt.where(
                Article.published_at <= datetime.combine(query.to_date, time.max)
            )

        if query.min_importance is not None:
            stmt = stmt.where(latest_importance_subq.c.score >= query.min_importance)

        if query.max_importance is not None:
            stmt = stmt.where(latest_importance_subq.c.score <= query.max_importance)

        if query.has_feedback is not None:
            stmt = stmt.where(has_feedback_expr if query.has_feedback else ~has_feedback_expr)

        if query.liked is not None:
            stmt = stmt.where(is_liked_expr if query.liked else ~is_liked_expr)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt)
        total = total or 0

        sort_map = {
            "published_at_desc": Article.published_at.desc().nullslast(),
            "published_at_asc": Article.published_at.asc().nullsfirst(),
            "importance_desc": latest_importance_subq.c.score.desc().nullslast(),
            "importance_asc": latest_importance_subq.c.score.asc().nullsfirst(),
        }

        stmt = stmt.order_by(sort_map[query.sort.value], Article.id.desc())
        stmt = stmt.offset((query.page - 1) * query.size).limit(query.size)

        result = await self.db.execute(stmt)
        rows = result.mappings().all()

        return [dict(row) for row in rows], total

    async def get_article_detail(self, user_id: int, article_id: int) -> Optional[Dict[str, Any]]:
        latest_summary_subq = (
            select(
                Summary.article_id.label("article_id"),
                Summary.summary_text.label("summary_text"),
                func.row_number()
                .over(
                    partition_by=Summary.article_id,
                    order_by=Summary.created_at.desc(),
                )
                .label("rn"),
            )
            .subquery()
        )

        latest_importance_subq = (
            select(
                ImportanceScore.article_id.label("article_id"),
                ImportanceScore.user_id.label("user_id"),
                ImportanceScore.score.label("score"),
                func.row_number()
                .over(
                    partition_by=(ImportanceScore.article_id, ImportanceScore.user_id),
                    order_by=ImportanceScore.created_at.desc(),
                )
                .label("rn"),
            )
            .subquery()
        )

        has_feedback_expr = exists(
            select(literal(1))
            .select_from(Feedback)
            .where(
                Feedback.article_id == Article.id,
                Feedback.user_id == user_id,
            )
        )

        is_liked_expr = exists(
            select(literal(1))
            .select_from(Feedback)
            .where(
                Feedback.article_id == Article.id,
                Feedback.user_id == user_id,
                Feedback.label == "LIKE",
            )
        )

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
                Article.id,
                Article.title,
                latest_summary_subq.c.summary_text.label("summary"),
                Article.content,
                Article.url,
                Article.publisher.label("source"),
                Article.language,
                Article.published_at,
                matched_keyword_subq.c.keyword_id,
                latest_importance_subq.c.score.label("importance"),
                case((is_liked_expr, True), else_=False).label("is_liked"),
                case((has_feedback_expr, True), else_=False).label("has_feedback"),
                Article.created_at,
            )
            .select_from(Article)
            .outerjoin(
                latest_summary_subq,
                and_(
                    latest_summary_subq.c.article_id == Article.id,
                    latest_summary_subq.c.rn == 1,
                ),
            )
            .outerjoin(
                latest_importance_subq,
                and_(
                    latest_importance_subq.c.article_id == Article.id,
                    latest_importance_subq.c.user_id == user_id,
                    latest_importance_subq.c.rn == 1,
                ),
            )
            .outerjoin(
                matched_keyword_subq,
                matched_keyword_subq.c.article_id == Article.id,
            )
            .where(Article.id == article_id)
        )

        result = await self.db.execute(stmt)
        row = result.mappings().first()
        if not row:
            return None
        return dict(row)

    async def article_exists(self, article_id: int) -> bool:
        stmt = select(func.count()).select_from(Article).where(Article.id == article_id)
        count = await self.db.scalar(stmt)
        return bool(count)

    async def has_article_access(self, user_id: int, article_id: int) -> bool:
        stmt = (
            select(func.count())
            .select_from(ArticleMatch)
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(
                ArticleMatch.article_id == article_id,
                Keyword.user_id == user_id,
            )
        )
        count = await self.db.scalar(stmt)
        return bool(count)
    
    
    
    async def get_article_importance(self, user_id: int, article_id: int) -> dict | None:
        stmt = (
            select(
                ImportanceScore.article_id,
                ImportanceScore.status,
                ImportanceScore.score,
                ImportanceScore.engine,
                ImportanceScore.version,
                ImportanceScore.scored_at,
                ImportanceScore.created_at,
                ImportanceScore.updated_at,
            )
            .where(ImportanceScore.article_id == article_id)
            .where(ImportanceScore.user_id == user_id)
            .where(ImportanceScore.is_current.is_(True))
            .limit(1)
        )

        result = await self.db.execute(stmt)
        row = result.mappings().first()
        if not row:
            return None

        row = dict(row)
        model_name = None
        if row.get("engine"):
            version = row.get("version")
            model_name = f"{row['engine']}-v{version}" if version is not None else row["engine"]

        return {
            "article_id": row["article_id"],
            "status": row["status"] or "PENDING",
            "score": row["score"],
            "model": model_name,
            "scored_at": row["scored_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }    

    async def upsert_article_feedback(
        self,
        user_id: int,
        article_id: int,
        action: str,
    ) -> dict:
        stmt = (
            select(Feedback)
            .where(Feedback.user_id == user_id)
            .where(Feedback.article_id == article_id)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        feedback = result.scalar_one_or_none()

        created = False

        if feedback is None:
            feedback = Feedback(
                user_id=user_id,
                article_id=article_id,
                label=action,
            )
            self.db.add(feedback)
            created = True
        else:
            feedback.label = action

        await self.db.flush()
        await self.db.refresh(feedback)

        updated_at = getattr(feedback, "updated_at", None) or feedback.created_at

        return {
            "article_id": article_id,
            "action": feedback.label,
            "created": created,
            "updated_at": updated_at,
        }
        
    async def get_my_feedback_by_article(
        self,
        user_id: int,
        article_id: int,
    ) -> dict | None:
        stmt = (
            select(Feedback)
            .where(Feedback.user_id == user_id)
            .where(Feedback.article_id == article_id)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        feedback = result.scalar_one_or_none()

        if feedback is None:
            return None

        updated_at = getattr(feedback, "updated_at", None) or feedback.created_at

        return {
            "feedback_id": feedback.id,
            "article_id": feedback.article_id,
            "action": feedback.label,
            "created_at": feedback.created_at,
            "updated_at": updated_at,
        }

    async def get_feedback_by_id(self, feedback_id: int) -> Feedback | None:
        stmt = select(Feedback).where(Feedback.id == feedback_id).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_feedback(self, feedback: Feedback) -> dict:
        feedback_id = feedback.id
        await self.db.delete(feedback)
        await self.db.flush()

        return {
            "deleted": True,
            "feedback_id": feedback_id,
        }

    async def validate_articles_exist_and_accessible(
        self,
        user_id: int,
        article_ids: list[int],
        keyword_id: int | None = None,
    ) -> None:
        if not article_ids:
            raise ValueError("VALIDATION_ERROR")

        stmt = (
            select(func.count(func.distinct(Article.id)))
            .select_from(Article)
            .join(ArticleMatch, ArticleMatch.article_id == Article.id)
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(Article.id.in_(article_ids))
            .where(Keyword.user_id == user_id)
        )

        if keyword_id is not None:
            stmt = stmt.where(ArticleMatch.keyword_id == keyword_id)

        count = await self.db.scalar(stmt)
        count = count or 0

        if count != len(set(article_ids)):
            raise ValueError("ARTICLE_NOT_FOUND_OR_FORBIDDEN")
    async def get_my_feedback_entity_by_article(
        self,
        user_id: int,
        article_id: int,
    ) -> Feedback | None:
        stmt = (
            select(Feedback)
            .where(Feedback.user_id == user_id)
            .where(Feedback.article_id == article_id)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_my_feedback_by_article(
        self,
        user_id: int,
        article_id: int,
    ) -> dict:
        feedback = await self.get_my_feedback_entity_by_article(
            user_id=user_id,
            article_id=article_id,
        )

        if feedback is None:
            raise ValueError("FEEDBACK_NOT_FOUND")

        await self.db.delete(feedback)
        await self.db.flush()

        return {
            "deleted": True,
            "article_id": article_id,
        }