from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.core.response import success_response
from app.models.user import User


router = APIRouter(
    prefix="/crawl-runs",
    tags=["crawl-runs"],
)

class CreateCrawlRunRequest(BaseModel):
    keyword_ids: list[int] | None = None
    force: bool = False


@router.post("")
async def create_crawl_run(
    request: Request,
    body: CreateCrawlRunRequest,
    current_user: User = Depends(get_current_user),
):
    return success_response(
        request,
        status_code=202,
        data={
            "crawl_run_id": 45,
            "status": "QUEUED",
        },
    )


@router.get("")
async def list_crawl_runs(
    request: Request,
    page: int = 1,
    size: int = 20,
    status: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"] | None = None,
    keyword_id: int | None = None,
    current_user: User = Depends(get_current_user),
):
    items = [
        {
            "id": 45,
            "status": "COMPLETED",
            "keyword_count": 3,
            "started_at": "2026-02-21T10:21:00Z",
            "finished_at": "2026-02-21T10:22:10Z",
            "created_at": "2026-02-21T10:20:55Z",
        }
    ]

    return success_response(
        request,
        data={
            "items": items,
            "page_info": {
                "page": page,
                "size": size,
                "total": len(items),
                "has_next": False,
            },
        },
    )


@router.get("/{run_id}")
async def get_crawl_run_detail(
    run_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return success_response(
        request,
        data={
            "id": run_id,
            "status": "COMPLETED",
            "keyword_count": 3,
            "article_count": 87,
            "started_at": "2026-02-21T10:21:00Z",
            "finished_at": "2026-02-21T10:22:10Z",
            "created_at": "2026-02-21T10:20:55Z",
        },
    )