import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.importance_score import ImportanceScore
from app.models.keyword import Keyword
from app.models.summary import Summary
from app.models.user import User

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/daily")
async def download_daily_report(
    keyword_id: int | None = Query(None, description="특정 키워드 필터 (없으면 전체)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    # 최신 요약 서브쿼리
    latest_summary_subq = (
        select(
            Summary.article_id,
            Summary.summary_text,
            func.row_number()
            .over(
                partition_by=Summary.article_id,
                order_by=Summary.created_at.desc(),
            )
            .label("rn"),
        ).subquery()
    )

    # 최신 중요도 점수 서브쿼리
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

    # 키워드 서브쿼리
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

    result = await db.execute(stmt)
    rows = result.mappings().all()

    # ── Excel 생성 ────────────────────────────────────────
    wb = Workbook()
    ws = wb.active
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ws.title = f"데일리 리포트 {today_str}"

    headers = [
        "기사 ID", "제목", "출처(언론사)", "게재일시",
        "키워드", "AI 중요도 점수", "AI 중요도 사유",
        "AI 요약", "원문 URL", "언어", "수집일시",
    ]

    # 헤더 스타일
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align

    ws.row_dimensions[1].height = 30

    # 데이터 행
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

        values = [
            row["id"],
            row["title"] or "",
            row["publisher"] or "",
            fmt_dt(row["published_at"]),
            row["keywords"] or "",
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
            for col_idx in range(1, len(headers) + 1):
                ws.cell(row=row_idx, column=col_idx).fill = PatternFill(
                    "solid", fgColor="EBF3FB"
                )

    # 열 너비
    col_widths = [10, 50, 18, 18, 20, 14, 40, 60, 50, 8, 18]
    for col_idx, width in enumerate(col_widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width

    # 틀 고정 (헤더 행)
    ws.freeze_panes = "A2"

    # 파일 반환
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    filename = f"daily_report_{today_str}.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
