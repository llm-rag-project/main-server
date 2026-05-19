import json
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, build_error
from app.models.importance_score import ImportanceScore
from app.models.scoring_feedback import ScoringFeedback
from app.repositories.article_repository import ArticleRepository
from app.repositories.importance_repository import ImportanceRepository
from app.services.dify_service import DifyService


class ImportanceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.importance_repository = ImportanceRepository(db)
        self.article_repository = ArticleRepository(db)
        self.dify_service = DifyService.from_settings()

    async def save_score(
        self,
        *,
        article_id: int,
        user_id: int,
        score: float,
        reason: str | None,
        engine: str = "dify-importance-workflow",
        version: int = 1,
    ) -> ImportanceScore:
        await self.db.execute(
            update(ImportanceScore)
            .where(
                ImportanceScore.article_id == article_id,
                ImportanceScore.user_id == user_id,
                ImportanceScore.is_current.is_(True),
            )
            .values(is_current=False)
        )

        row = ImportanceScore(
            article_id=article_id,
            user_id=user_id,
            score=score,
            reason=reason,
            status="COMPLETED",
            scored_at=datetime.now(timezone.utc),
            engine=engine,
            version=version,
            is_current=True,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def save_scoring_feedback(
        self,
        *,
        user_id: int,
        article_id: int,
        original_score: int,
        user_score: int,
        reason: str,
    ) -> ScoringFeedback:
        await self.article_repository.validate_articles_exist_and_accessible(
            user_id=user_id,
            article_ids=[article_id],
        )
        row = await self.importance_repository.save_scoring_feedback(
            user_id=user_id,
            article_id=article_id,
            original_score=original_score,
            user_score=user_score,
            reason=reason,
        )
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def get_importance_list(self, user_id: int, query):
        return await self.importance_repository.get_importance_list(
            user_id=user_id,
            query=query,
        )

    async def get_article_importance(self, user_id: int, article_id: int):
        await self.article_repository.validate_articles_exist_and_accessible(
            user_id=user_id,
            article_ids=[article_id],
        )

        result = await self.importance_repository.get_current_score(
            user_id=user_id,
            article_id=article_id,
        )

        if result is None:
            return {
                "article_id": article_id,
                "score": None,
                "reason": None,
                "status": "NOT_FOUND",
            }

        return result

    _DIFY_BATCH_SIZE = 9
    _SCORING_LIMIT = 10

    async def run_importance_scoring(
        self,
        user_id: int,
        article_ids: list[int],
        job_id: str | None = None,
    ) -> dict:
        from app.core.job_store import update_job

        def _upd(progress: int, message: str) -> None:
            """job_id가 있을 때만 진행률 업데이트."""
            if job_id:
                update_job(job_id, progress=progress, message=message)

        _upd(5, "기사 접근 권한 확인 중...")
        await self.article_repository.validate_articles_exist_and_accessible(
            user_id=user_id,
            article_ids=article_ids,
        )

        # 이미 채점된 기사 제외
        _upd(10, "이미 채점된 기사 확인 중...")
        already_scored = await self.importance_repository.get_already_scored_article_ids(
            user_id=user_id,
            article_ids=article_ids,
        )
        unscored_ids = [aid for aid in article_ids if aid not in already_scored]

        # 최대 10건만 처리
        ids_to_score = unscored_ids[: self._SCORING_LIMIT]
        remaining_count = len(unscored_ids) - len(ids_to_score)

        _upd(
            15,
            f"채점 대상 {len(ids_to_score)}건 확인 완료"
            + (f" (이미 채점 {len(already_scored)}건 제외)" if already_scored else ""),
        )

        articles = await self.article_repository.get_articles_for_importance_scoring(
            user_id=user_id,
            article_ids=ids_to_score,
        ) if ids_to_score else []

        saved_items = []

        if articles:
            feedback_rows = await self.importance_repository.get_feedback_history(user_id)
            feedback_history = (
                json.dumps(feedback_rows, ensure_ascii=False) if feedback_rows else ""
            )

            batches = [
                articles[i: i + self._DIFY_BATCH_SIZE]
                for i in range(0, len(articles), self._DIFY_BATCH_SIZE)
            ]
            total_batches = len(batches)

            for batch_idx, batch in enumerate(batches):
                # 진행률: 20% ~ 90% 구간을 배치 수로 균등 분배
                progress_before = 20 + int((batch_idx / total_batches) * 70)
                _upd(
                    progress_before,
                    f"🤖 AI 분석 중... 배치 {batch_idx + 1}/{total_batches} 처리 중",
                )

                articles_payload = json.dumps(
                    [
                        {
                            "article_id": a["article_id"],
                            "title": a["title"],
                            "content": a["content"],
                        }
                        for a in batch
                    ],
                    ensure_ascii=False,
                )

                dify_result = await self.dify_service.run_importance_workflow(
                    user_id=user_id,
                    articles=articles_payload,
                    feedback_history=feedback_history,
                )

                data = dify_result.get("data") or {}
                items = data.get("items") or []

                if not items or not isinstance(items, list):
                    raise build_error(ErrorCode.UPSTREAM_ERROR, "Dify returned empty or invalid items")

                progress_after = 20 + int(((batch_idx + 1) / total_batches) * 70)
                completed_count = sum(len(batches[i]) for i in range(batch_idx + 1))
                _upd(
                    progress_after,
                    f"✅ 배치 {batch_idx + 1}/{total_batches} 완료 — {completed_count}건 처리",
                )

                for item in items:
                    article_id = item.get("article_id")
                    score = item.get("score")
                    reason = item.get("reason")

                    if article_id is None or score is None:
                        raise build_error(
                            ErrorCode.UPSTREAM_ERROR,
                            f"Invalid importance item from Dify: {item}",
                        )

                    row = await self.save_score(
                        article_id=int(article_id),
                        user_id=user_id,
                        score=float(score),
                        reason=reason,
                    )
                    saved_items.append(
                        {
                            "article_id": row.article_id,
                            "score": row.score,
                            "reason": row.reason,
                        }
                    )

        _upd(95, "💾 결과 저장 중...")
        await self.db.commit()

        return {
            "items": saved_items,
            "already_scored_count": len(already_scored),
            "remaining_count": remaining_count,
        }
