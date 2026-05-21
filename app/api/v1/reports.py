import io
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.response import success_response
from app.models.article import Article
from app.models.article_analysis import ArticleAnalysis
from app.models.article_match import ArticleMatch
from app.models.importance_score import ImportanceScore
from app.models.keyword import Keyword
from app.models.summary import Summary
from app.models.user import User
from app.services.email_service import EmailService

router = APIRouter(prefix="/reports", tags=["reports"])

HEADERS = [
    "기사 ID", "제목", "출처(언론사)", "게재일시",
    "키워드", "AI 감성", "홍보성 여부",
    "AI 중요도 점수", "AI 중요도 사유",
    "AI 요약", "원문 URL", "언어", "수집일시",
]
COL_WIDTHS = [10, 50, 18, 18, 20, 12, 12, 14, 40, 60, 50, 8, 18]


class EmailReportRequest(BaseModel):
    to_emails: List[EmailStr]
    keyword_id: int | None = None
    keyword_name: str | None = None


def _build_query(current_user, keyword_id=None):
    """두 엔드포인트가 공유하는 쿼리 빌더."""

    latest_summary_subq = (
        select(
            Summary.article_id,
            Summary.summary_text,
            func.row_number()
            .over(partition_by=Summary.article_id, order_by=Summary.created_at.desc())
            .label("rn"),
        ).subquery()
    )

    latest_importance_subq = (
        select(
            ImportanceScore.article_id,
            ImportanceScore.score,
            ImportanceScore.reason.label("importance_reason"),
            func.row_number()
            .over(
                partition_by=ImportanceScore.article_id,
                order_by=ImportanceScore.created_at.desc(),
            )
            .label("rn"),
        )
        .where(ImportanceScore.user_id == current_user.id)
        .where(ImportanceScore.is_current.is_(True))
        .subquery()
    )

    keyword_subq = (
        select(
            ArticleMatch.article_id,
            func.string_agg(Keyword.keyword_text, ", ").label("keywords"),
        )
        .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
        .where(Keyword.user_id == current_user.id)
        .group_by(ArticleMatch.article_id)
        .subquery()
    )

    stmt = (
        select(
            Article.id,
            Article.title,
            Article.publisher,
            Article.published_at,
            Article.url,
            Article.language,
            Article.created_at,
            keyword_subq.c.keywords,
            ArticleAnalysis.sentiment,
            ArticleAnalysis.is_promotion,
            latest_importance_subq.c.score,
            latest_importance_subq.c.importance_reason,
            latest_summary_subq.c.summary_text,
        )
        .outerjoin(keyword_subq, keyword_subq.c.article_id == Article.id)
        .outerjoin(
            latest_importance_subq,
            (latest_importance_subq.c.article_id == Article.id)
            & (latest_importance_subq.c.rn == 1),
        )
        .outerjoin(
            latest_summary_subq,
            (latest_summary_subq.c.article_id == Article.id)
            & (latest_summary_subq.c.rn == 1),
        )
        .outerjoin(ArticleAnalysis, ArticleAnalysis.article_id == Article.id)
        .where(
            Article.id.in_(
                select(ArticleMatch.article_id)
                .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
                .where(Keyword.user_id == current_user.id)
            )
        )
        .order_by(Article.published_at.desc().nullslast())
    )

    if keyword_id:
        stmt = stmt.where(
            Article.id.in_(
                select(ArticleMatch.article_id)
                .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
                .where(
                    ArticleMatch.keyword_id == keyword_id,
                    Keyword.user_id == current_user.id,
                )
            )
        )

    return stmt


def _build_excel(rows) -> Workbook:
    """rows → 스타일 적용된 Workbook 반환."""
    wb = Workbook()
    ws = wb.active
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ws.title = f"데일리 리포트 {today_str}"

    # 헤더 스타일
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_idx, header in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align
    ws.row_dimensions[1].height = 30

    body_align = Alignment(vertical="top", wrap_text=True)

    for row_idx, row in enumerate(rows, start=2):
        def fmt_dt(val):
            if val is None:
                return ""
            if hasattr(val, "strftime"):
                return val.strftime("%Y-%m-%d %H:%M")
            return str(val)

        score = row["score"]
        score_display = f"{float(score):.1f}" if score is not None else ""

        # 감성: None이면 빈 문자열
        sentiment = row["sentiment"] or ""

        # 홍보성: True→"O", False→"X", None→""
        is_promotion = row["is_promotion"]
        if is_promotion is True:
            promotion_display = "O"
        elif is_promotion is False:
            promotion_display = "X"
        else:
            promotion_display = ""

        values = [
            row["id"],
            row["title"] or "",
            row["publisher"] or "",
            fmt_dt(row["published_at"]),
            row["keywords"] or "",
            sentiment,
            promotion_display,
            score_display,
            row["importance_reason"] or "",
            row["summary_text"] or "",
            row["url"] or "",
            row["language"] or "",
            fmt_dt(row["created_at"]),
        ]

        for col_idx, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.alignment = body_align

        # 짝수 행 배경
        if row_idx % 2 == 0:
            for col_idx in range(1, len(HEADERS) + 1):
                ws.cell(row=row_idx, column=col_idx).fill = PatternFill(
                    "solid", fgColor="EBF3FB"
                )

    # 열 너비
    for col_idx, width in enumerate(COL_WIDTHS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width

    ws.freeze_panes = "A2"
    return wb


@router.get("/daily")
async def download_daily_report(
    keyword_id: int | None = Query(None, description="특정 키워드 필터 (없으면 전체)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    stmt = _build_query(current_user, keyword_id=keyword_id)
    result = await db.execute(stmt)
    rows = result.mappings().all()

    wb = _build_excel(rows)
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"daily_report_{today_str}.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/email")
async def send_daily_report_email(
    request: Request,
    body: EmailReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    """데일리 리포트를 Excel로 생성하여 이메일로 발송합니다."""
    stmt = _build_query(current_user, keyword_id=body.keyword_id)
    result = await db.execute(stmt)
    rows = result.mappings().all()

    wb = _build_excel(rows)
    stream = io.BytesIO()
    wb.save(stream)
    excel_bytes = stream.getvalue()

    email_service = EmailService()
    email_service.send_daily_report(
        to_emails=body.to_emails,
        excel_bytes=excel_bytes,
        keyword_name=body.keyword_name,
    )

    return success_response(
        request=request,
        data={
            "sent_to": body.to_emails,
            "article_count": len(rows),
            "message": f"{len(body.to_emails)}명에게 데일리 리포트를 발송했습니다.",
        },
    )
