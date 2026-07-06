from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.errors import ErrorCode, build_error
from app.core.response import success_response
from app.repositories.article_repository import ArticleRepository
from app.schemas.ai import (
    AIChatRequest,
    ImportanceBatchRequest,
    ImportanceItemResponse,
    SummaryRequest,
)
from app.services.article_service import ArticleService
from app.services.dify_service import DifyService
from app.services.importance_service import ImportanceService
from app.services.summary_service import SummaryService

router = APIRouter(prefix="/ai", tags=["AI"])


def get_dify_service() -> DifyService:
    return DifyService.from_settings()


@router.post("/chat")
async def chat(
    request: Request,
    payload: AIChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_dev_user),
):
    dify_service = get_dify_service()
    article_service = ArticleService(db)

    if payload.article_id is not None:
        article = await article_service.get_article_by_id(payload.article_id)
        if not article:
            raise build_error(ErrorCode.NOT_FOUND, "기사를 찾을 수 없습니다.")

    try:
        result = await dify_service.send_chat_message(
            user_id=current_user.id,
            message=payload.message,
            article_id=payload.article_id,
            conversation_id=payload.conversation_id or "",
        )
    except Exception as e:
        raise build_error(ErrorCode.UPSTREAM_ERROR, f"채팅 호출 실패: {e}") from e

    return success_response(request, data={
        "answer": result.get("answer", "응답이 없습니다."),
        "conversation_id": result.get("conversation_id"),
    })


@router.post("/summary")
async def summarize_article(
    request: Request,
    payload: SummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_dev_user),
):
    from app.core.job_store import complete_job, create_job, fail_job, update_job

    job_id = create_job("summary", job_id=payload.job_id)
    update_job(job_id, progress=5, message="기사 내용을 불러오고 있습니다.")

    dify_service = get_dify_service()
    article_service = ArticleService(db)
    summary_service = SummaryService(db)

    article = await article_service.get_article_by_id(payload.article_id)
    if not article:
        fail_job(job_id, "기사를 찾을 수 없습니다.")
        raise build_error(ErrorCode.NOT_FOUND, "기사를 찾을 수 없습니다.")

    update_job(job_id, progress=15, message="AI가 기사를 읽고 핵심 내용을 정리하고 있습니다.")

    try:
        result = await dify_service.run_summary_workflow(
            user_id=current_user.id,
            article_id=article.id,
            title=article.title or "",
            content=article.content or "",
        )
    except Exception as e:
        fail_job(job_id, f"요약 workflow 호출 실패: {e}")
        raise build_error(ErrorCode.UPSTREAM_ERROR, f"요약 workflow 호출 실패: {e}") from e

    summary_text = result.get("summary")
    if not summary_text:
        fail_job(job_id, "요약 결과를 찾을 수 없습니다.")
        raise build_error(ErrorCode.UPSTREAM_ERROR, "요약 결과를 찾을 수 없습니다.")

    update_job(job_id, progress=85, message="요약이 완성되었습니다. 저장하고 있습니다.")

    try:
        saved = await summary_service.save_summary(
            article_id=article.id,
            summary_text=summary_text,
            language="ko",
            model_name="dify-summary-workflow",
        )
        await db.commit()
        await db.refresh(saved)
    except Exception as e:
        await db.rollback()
        fail_job(job_id, f"요약 저장 실패: {e}")
        raise build_error(ErrorCode.UPSTREAM_ERROR, f"요약 저장 실패: {e}") from e

    complete_job(job_id)
    return success_response(request, data={
        "article_id": saved.article_id,
        "summary_text": saved.summary_text,
        "language": saved.language,
        "model_name": saved.model_name,
        "job_id": job_id,
    })


@router.post("/scoring")
async def score_articles_by_keyword(
    request: Request,
    payload: ImportanceBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_dev_user),
):
    article_repo = ArticleRepository(db)
    article_ids = await article_repo.get_article_ids_by_keyword(
        user_id=current_user.id,
        keyword_id=payload.keyword_id,
    )
    if not article_ids:
        return success_response(request, data={
            "keyword_id": payload.keyword_id,
            "processed_count": 0,
            "results": [],
        })

    importance_service = ImportanceService(db)
    try:
        result = await importance_service.run_importance_scoring(
            user_id=current_user.id,
            article_ids=article_ids,
        )
    except Exception as e:
        raise build_error(ErrorCode.UPSTREAM_ERROR, f"중요도 workflow 호출 실패: {e}") from e

    response_items = [
        ImportanceItemResponse(
            article_id=int(item["article_id"]),
            score=float(item["score"]),
            reason=item.get("reason"),
        )
        for item in result.get("items", [])
        if item.get("article_id") is not None and item.get("score") is not None
    ]

    return success_response(request, data={
        "keyword_id": payload.keyword_id,
        "processed_count": len(response_items),
        "results": [item.model_dump() for item in response_items],
    })
