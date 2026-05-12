import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.errors import ErrorCode, build_error
from app.core.response import success_response
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
        raise build_error(ErrorCode.UPSTREAM_ERROR, f"채팅 호출 실패: {e}")

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
    dify_service = get_dify_service()
    article_service = ArticleService(db)
    summary_service = SummaryService(db)

    article = await article_service.get_article_by_id(payload.article_id)
    if not article:
        raise build_error(ErrorCode.NOT_FOUND, "기사를 찾을 수 없습니다.")

    try:
        result = await dify_service.run_summary_workflow(
            user_id=current_user.id,
            article_id=article.id,
            title=article.title or "",
            content=article.content or "",
        )
    except Exception as e:
        raise build_error(ErrorCode.UPSTREAM_ERROR, f"요약 workflow 호출 실패: {e}")

    summary_text = result.get("summary")
    if not summary_text:
        raise build_error(ErrorCode.UPSTREAM_ERROR, "요약 결과를 찾을 수 없습니다.")

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
        raise build_error(ErrorCode.UPSTREAM_ERROR, f"요약 저장 실패: {e}")

    return success_response(request, data={
        "article_id": saved.article_id,
        "summary_text": saved.summary_text,
        "language": saved.language,
        "model_name": saved.model_name,
    })


@router.post("/scoring")
async def score_articles_by_keyword(
    request: Request,
    payload: ImportanceBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_dev_user),
):
    dify_service = get_dify_service()
    article_service = ArticleService(db)
    importance_service = ImportanceService(db)

    articles = await article_service.get_articles_by_keyword_id(payload.keyword_id)
    if not articles:
        return success_response(request, data={
            "keyword_id": payload.keyword_id,
            "processed_count": 0,
            "results": [],
        })

    articles_payload = json.dumps(
        [
            {
                "article_id": article.id,
                "title": article.title or "",
                "content": article.content or "",
            }
            for article in articles
        ],
        ensure_ascii=False,
    )

    try:
        result = await dify_service.run_importance_workflow(
            user_id=current_user.id,
            articles=articles_payload,
        )
    except Exception as e:
        raise build_error(ErrorCode.UPSTREAM_ERROR, f"중요도 workflow 호출 실패: {e}")

    items = result.get("data", {}).get("items", [])
    if not items:
        return success_response(request, data={
            "keyword_id": payload.keyword_id,
            "processed_count": 0,
            "results": [],
        })

    try:
        response_items: list[ImportanceItemResponse] = []
        for item in items:
            article_id = item.get("article_id")
            score = item.get("score")
            if article_id is None or score is None:
                continue
            saved = await importance_service.save_score(
                article_id=int(article_id),
                user_id=current_user.id,
                score=float(score),
                reason=item.get("reason"),
                engine="dify-importance-workflow",
                version=1,
            )
            response_items.append(
                ImportanceItemResponse(
                    article_id=saved.article_id,
                    score=saved.score,
                    reason=saved.reason,
                )
            )
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise build_error(ErrorCode.UPSTREAM_ERROR, f"중요도 저장 실패: {e}")

    return success_response(request, data={
        "keyword_id": payload.keyword_id,
        "processed_count": len(response_items),
        "results": [item.model_dump() for item in response_items],
    })
