from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user_or_dev_user
from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    SummaryRequest,
    SummaryResponse,
    ImportanceBatchRequest,
    ImportanceBatchResponse,
    ImportanceItemResponse,
)
from app.services.article_service import ArticleService
from app.services.dify_service import DifyService
from app.services.importance_service import ImportanceService
from app.services.summary_service import SummaryService
import app.core.config
from app.api.v1.auth import get_current_user


router = APIRouter(prefix="/ai", tags=["AI"])


def get_dify_service() -> DifyService:
    return DifyService(
        base_url=app.core.config.settings.AI_BASE_URL,
        chatflow_api_key=app.core.config.settings.CHATFLOW_API_KEY,
        summary_workflow_api_key=app.core.config.settings.SUMMARY_WORKFLOW_API_KEY,
        importance_workflow_api_key=app.core.config.settings.SCORING_WORKFLOW_API_KEY,
        timeout=30.0,
    )


@router.post("/chat", response_model=AIChatResponse)
async def chat(
    request: AIChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    dify_service = get_dify_service()
    article_service = ArticleService(db)

    if request.article_id is not None:
        article = await article_service.get_article_by_id(request.article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="기사를 찾을 수 없습니다.",
            )

    try:
        result = await dify_service.send_chat_message(
            user_id=current_user.id,
            message=request.message,
            article_id=request.article_id,
            conversation_id=request.conversation_id or "",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"채팅 호출 실패: {e}",
        )

    return AIChatResponse(
        answer=result.get("answer", "응답이 없습니다."),
        conversation_id=result.get("conversation_id"),
    )


@router.post("/summary", response_model=SummaryResponse)
async def summarize_article(
    request: SummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    dify_service = get_dify_service()
    article_service = ArticleService(db)
    summary_service = SummaryService(db)

    article = await article_service.get_article_by_id(request.article_id)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="기사를 찾을 수 없습니다.",
        )

    try:
        result = await dify_service.run_summary_workflow(
            user_id=current_user.id,
            article_id=article.id,
            title=article.title,
            content=article.content,
            publisher=article.publisher,
            published_at=article.published_at.isoformat() if article.published_at else None,
        )

        outputs = result.get("outputs") or {}
        summary_text = (
            outputs.get("summary")
            or outputs.get("summary_text")
            or outputs.get("result")
            or outputs.get("text")
        )

        if not summary_text:
            raise ValueError("요약 결과를 찾을 수 없습니다.")

        saved = await summary_service.save_summary(
            article_id=article.id,
            summary_text=summary_text,
            language="ko",
            model_name="dify-summary-workflow",
        )
        await db.commit()
        await db.refresh(saved)

        return SummaryResponse(
            article_id=saved.article_id,
            summary_text=saved.summary_text,
            language=saved.language,
            model_name=saved.model_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"요약 workflow 호출 실패: {e}",
        )


@router.post("/scoring", response_model=ImportanceBatchResponse)
async def score_articles_by_keyword(
    request: ImportanceBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    dify_service = get_dify_service()
    article_service = ArticleService(db)
    importance_service = ImportanceService(db)

    articles = await article_service.get_articles_by_keyword_id(request.keyword_id)
    if not articles:
        return ImportanceBatchResponse(
            keyword_id=request.keyword_id,
            processed_count=0,
            results=[],
        )

    response_items = []

    try:
        for article in articles:
            result = await dify_service.run_importance_workflow(
                user_id=current_user.id,
                article_id=article.id,
                title=article.title,
                content=article.content,
                publisher=article.publisher,
                published_at=article.published_at.isoformat() if article.published_at else None,
            )

            outputs = result.get("outputs") or {}
            score = outputs.get("score")
            reason = outputs.get("reason")

            if score is None:
                continue

            saved = await importance_service.save_score(
                article_id=article.id,
                user_id=current_user.id,
                score=float(score),
                reason=reason,
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

        return ImportanceBatchResponse(
            keyword_id=request.keyword_id,
            processed_count=len(response_items),
            results=response_items,
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"중요도 workflow 호출 실패: {e}",
        )