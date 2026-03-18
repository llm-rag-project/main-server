from app.repositories.importance_repository import ImportanceRepository
from app.schemas.importance import (
    ImportanceListItem,
    ImportanceListQuery,
    ImportanceListResponse,
    PageInfo,
)


class ImportanceService:
    def __init__(self, repository: ImportanceRepository):
        self.repository = repository

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