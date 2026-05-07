from app.repositories.stats_repository import StatsRepository


class StatsService:
    def __init__(self, repo: StatsRepository):
        self.repo = repo

    async def get_article_stats(self, user_id: int, days: int = 7) -> dict:
        by_keyword = await self.repo.get_article_count_by_keyword(
            user_id=user_id, days=days
        )
        by_date = await self.repo.get_article_count_by_date(
            user_id=user_id, days=days
        )
        by_keyword_date = await self.repo.get_article_count_by_date_per_keyword(
            user_id=user_id, days=days
        )

        return {
            "days": days,
            "by_keyword": by_keyword,            # 파이/바 차트용
            "by_date": by_date,                  # 전체 라인 차트용
            "by_keyword_date": by_keyword_date,  # 키워드별 비교 라인 차트용
        }