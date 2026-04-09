import json

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


router = APIRouter(prefix="/ai", tags=["AI"])


def get_dify_service() -> DifyService:
    return DifyService.from_settings()




@router.post("/chat", response_model=AIChatResponse)
async def chat(
    request: AIChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_dev_user),
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

        result_data = result.get("data") or {}

        return AIChatResponse(
            answer=result_data.get("answer", "응답이 없습니다."),
            conversation_id=result_data.get("conversation_id"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"채팅 호출 실패: {e}",
        )


@router.post("/summary", response_model=SummaryResponse)
async def summarize_article(
    request: SummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_dev_user),
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
        articles_payload = json.dumps(
            [
                {
                    "article_id": article.id,
                    "title": article.title or "",
                    "content": article.content or "",
                }
            ],
            ensure_ascii=False,
        )

        result = await dify_service.run_summary_workflow(
            user_id=current_user.id,
            message="이 기사를 한국어로 핵심만 간결하게 요약해줘. 반드시 JSON 형식으로 반환해줘.",
            articles=articles_payload,
        )

        summary_text = result.get("data", {}).get("items", [])

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
    current_user=Depends(get_current_user_or_dev_user),
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

    try:
        # ✅ 모든 기사 한 번에 payload 생성
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

        # ✅ Dify 한 번만 호출
        result = await dify_service.run_importance_workflow(
            user_id=current_user.id,
            articles=articles_payload,
        )

        items = result.get("data", {}).get("items", [])

        if not items:
            return ImportanceBatchResponse(
                keyword_id=request.keyword_id,
                processed_count=0,
                results=[],
            )

        response_items: list[ImportanceItemResponse] = []

        # 🔥 여러 개 결과 처리
        for item in items:
            article_id = item.get("article_id")
            score = item.get("score")
            reason = item.get("reason")

            if article_id is None or score is None:
                continue

            saved = await importance_service.save_score(
                article_id=int(article_id),
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