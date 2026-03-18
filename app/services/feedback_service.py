from app.repositories.feedback_repository import FeedbackRepository
from app.schemas.feedbacks import RankingFeedbackRequest, RankingFeedbackResponse


class FeedbackService:
    def __init__(self, repository: FeedbackRepository):
        self.repository = repository

    async def save_ranking_feedback(
        self,
        user_id: int,
        payload: RankingFeedbackRequest,
    ) -> RankingFeedbackResponse:
        await self.repository.validate_articles_exist_and_accessible(
            user_id=user_id,
            article_ids=payload.article_ids,
            keyword_id=payload.keyword_id,
        )

        result = await self.repository.save_ranking_feedback(
            user_id=user_id,
            article_ids=payload.article_ids,
            keyword_id=payload.keyword_id,
        )
        return RankingFeedbackResponse(**result)