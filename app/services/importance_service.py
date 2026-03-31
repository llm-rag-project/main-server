from app.core.errors import ErrorCode, build_error
from app.repositories.article_repository import ArticleRepository
from app.repositories.importance_repository import ImportanceRepository
from app.schemas.importance import (
    ImportanceListItem,
    ImportanceListQuery,
    ImportanceListResponse,
    ImportanceRunItem,
    ImportanceRunResponse,
    PageInfo,
)
from app.services.dify_service import DifyService


class ImportanceService:
    def __init__(
        self,
        repository: ImportanceRepository,
        article_repository: ArticleRepository | None = None,
        dify_service: DifyService | None = None,
    ):
        self.repository = repository
        self.article_repository = article_repository
        self.dify_service = dify_service or DifyService()

    async def get_importance_list(self, user_id: int, query: ImportanceListQuery) -> ImportanceListResponse:
        rows, total = await self.repository.get_importance_list(user_id=user_id, query=query)
        items = [ImportanceListItem(**row) for row in rows]
        has_next = query.page * query.size < total

        return ImportanceListResponse(
            items=items,
            page_info=PageInfo(
                page=query.page,
                size=query.size,
                total=total,
                has_next=has_next,
            ),
        )

    async def run_importance_scoring(
        self,
        user_id: int,
        article_ids: list[int],
    ) -> ImportanceRunResponse:
        if not self.article_repository:
            raise build_error(ErrorCode.INTERNAL_ERROR, "Article repository is required")

        articles = await self.article_repository.get_articles_for_importance_scoring(
            user_id=user_id,
            article_ids=article_ids,
        )

        if not articles:
            raise build_error(ErrorCode.NOT_FOUND, "No accessible articles found")

        if len(articles) != len(set(article_ids)):
            raise build_error(
                ErrorCode.FORBIDDEN,
                "Some articles do not exist or are not accessible",
            )

        try:
            workflow_result = await self.dify_service.run_importance_workflow(
                user_id=user_id,
                articles=articles,
            )
        except RuntimeError as e:
            if str(e) == "UPSTREAM_ERROR":
                raise build_error(ErrorCode.UPSTREAM_ERROR, "Failed to execute importance workflow")
            raise build_error(ErrorCode.UPSTREAM_ERROR, str(e))

        items = workflow_result.get("items") or []
        if not items:
            raise build_error(ErrorCode.UPSTREAM_ERROR, "Importance workflow returned empty result")

        article_id_list = [item["article_id"] for item in items]
        await self.repository.clear_current_scores(user_id=user_id, article_ids=article_id_list)
        await self.repository.bulk_insert_scores(user_id=user_id, items=items)

        return ImportanceRunResponse(
            workflow_run_id=workflow_result.get("workflow_run_id"),
            task_id=workflow_result.get("task_id"),
            items=[ImportanceRunItem(**item) for item in items],
        )