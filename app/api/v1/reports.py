import io
from datetime import datetime, timezone
from html import escape
from typing import Iterable, List

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
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
from app.models.social_metric import SocialMetric
from app.models.summary import Summary
from app.models.user import User
from app.services.email_service import EmailService

router = APIRouter(prefix="/reports", tags=["reports"])

BLUE = "3B82F6"
BLUE_DARK = "1E3A8A"
BLUE_SOFT = "EFF6FF"
LINE = "DBEAFE"
HEADER_FILL = "2563EB"
TEXT = "172033"
MUTED = "64748B"
GREEN = "16A34A"
RED = "DC2626"
AMBER = "D97706"

ARTICLE_HEADERS = [
    "기사 ID",
    "제목",
    "출처",
    "게시 일시",
    "키워드",
    "AI 감성",
    "홍보성",
    "중요도",
    "중요도 사유",
    "AI 요약",
    "원문 URL",
    "언어",
    "수집 일시",
]
ARTICLE_WIDTHS = [10, 52, 18, 18, 22, 12, 10, 10, 44, 62, 52, 8, 18]


class EmailReportRequest(BaseModel):
    to_emails: List[EmailStr]
    keyword_id: int | None = None
    keyword_name: str | None = None


def _fmt_dt(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _score_value(row) -> float | None:
    score = row["score"]
    return float(score) if score is not None else None


def _sentiment_key(value: str | None) -> str:
    text = str(value or "").lower()
    if "부정" in text or "negative" in text:
        return "부정"
    if "긍정" in text or "positive" in text:
        return "긍정"
    if "중립" in text or "neutral" in text:
        return "중립"
    return "미분석"


def _promotion_label(value) -> str:
    if value is True:
        return "홍보성"
    if value is False:
        return "일반"
    return "미분석"


async def _keyword_name(db: AsyncSession, current_user: User, keyword_id: int | None) -> str | None:
    if not keyword_id:
        return None
    result = await db.execute(
        select(Keyword.keyword_text).where(
            Keyword.id == keyword_id,
            Keyword.user_id == current_user.id,
        )
    )
    return result.scalar_one_or_none()


def _build_query(current_user: User, keyword_id: int | None = None):
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
        .order_by(Article.published_at.desc().nullslast(), Article.id.desc())
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


async def _get_social_report_rows(db: AsyncSession, current_user: User, keyword_id: int | None = None) -> list[dict]:
    latest_subq = (
        select(
            SocialMetric.keyword_id,
            SocialMetric.source,
            func.max(SocialMetric.sampled_at).label("sampled_at"),
        )
        .where(SocialMetric.user_id == current_user.id)
        .group_by(SocialMetric.keyword_id, SocialMetric.source)
        .subquery()
    )
    stmt = (
        select(
            SocialMetric.keyword_text,
            SocialMetric.source,
            SocialMetric.mention_count,
            SocialMetric.positive_hint_count,
            SocialMetric.negative_hint_count,
            SocialMetric.sampled_at,
        )
        .join(
            latest_subq,
            (latest_subq.c.keyword_id == SocialMetric.keyword_id)
            & (latest_subq.c.source == SocialMetric.source)
            & (latest_subq.c.sampled_at == SocialMetric.sampled_at),
        )
        .where(SocialMetric.user_id == current_user.id)
    )
    if keyword_id:
        stmt = stmt.where(SocialMetric.keyword_id == keyword_id)
    result = await db.execute(stmt)
    return [dict(row) for row in result.mappings().all()]


def _report_context(rows: Iterable[dict], keyword_name: str | None = None, social_rows: list[dict] | None = None) -> dict:
    rows = list(rows)
    keyword_counts: dict[str, int] = {}
    sentiment_counts = {"긍정": 0, "중립": 0, "부정": 0, "미분석": 0}
    promotion_counts = {"홍보성": 0, "일반": 0, "미분석": 0}
    daily_counts: dict[str, int] = {}
    scores: list[float] = []
    summarized_count = 0
    social_source_counts: dict[str, int] = {}
    social_total = 0
    social_positive = 0
    social_negative = 0

    for row in rows:
        for keyword in (row["keywords"] or "미분류").split(","):
            key = keyword.strip() or "미분류"
            keyword_counts[key] = keyword_counts.get(key, 0) + 1

        sentiment_counts[_sentiment_key(row["sentiment"])] += 1
        promotion_counts[_promotion_label(row["is_promotion"])] += 1

        date_key = _fmt_dt(row["published_at"])[:10] or "날짜 없음"
        daily_counts[date_key] = daily_counts.get(date_key, 0) + 1

        score = _score_value(row)
        if score is not None:
            scores.append(score)
        if row["summary_text"]:
            summarized_count += 1

    for row in social_rows or []:
        source = row["source"] or "unknown"
        count = int(row["mention_count"] or 0)
        social_source_counts[source] = social_source_counts.get(source, 0) + count
        social_total += count
        social_positive += int(row["positive_hint_count"] or 0)
        social_negative += int(row["negative_hint_count"] or 0)

    top_articles = sorted(
        [row for row in rows if _score_value(row) is not None],
        key=lambda item: _score_value(item) or 0,
        reverse=True,
    )[:8]
    negative_rate = round((sentiment_counts["부정"] / len(rows)) * 100) if rows else 0
    promotion_rate = round((promotion_counts["홍보성"] / len(rows)) * 100) if rows else 0
    social_negative_rate = round((social_negative / social_total) * 100) if social_total else 0

    return {
        "keyword_name": keyword_name,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "total_count": len(rows),
        "summary_count": summarized_count,
        "scored_count": len(scores),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "negative_rate": negative_rate,
        "promotion_rate": promotion_rate,
        "social_total": social_total,
        "social_positive": social_positive,
        "social_negative": social_negative,
        "social_negative_rate": social_negative_rate,
        "keyword_counts": sorted(keyword_counts.items(), key=lambda item: item[1], reverse=True)[:10],
        "sentiment_counts": [(k, v) for k, v in sentiment_counts.items() if v],
        "promotion_counts": [(k, v) for k, v in promotion_counts.items() if v],
        "daily_counts": sorted(daily_counts.items()),
        "social_source_counts": sorted(social_source_counts.items(), key=lambda item: item[1], reverse=True),
        "top_articles": top_articles,
        "executive_summary": _executive_summary(
            keyword_name=keyword_name,
            total_count=len(rows),
            negative_rate=negative_rate,
            promotion_rate=promotion_rate,
            social_total=social_total,
            social_negative_rate=social_negative_rate,
            top_articles=top_articles,
        ),
    }


def _executive_summary(
    *,
    keyword_name: str | None,
    total_count: int,
    negative_rate: int,
    promotion_rate: int,
    social_total: int,
    social_negative_rate: int,
    top_articles: list,
) -> list[str]:
    label = keyword_name or "전체 키워드"
    lines = [f"{label} 기준 수집 기사 {total_count}건을 분석했습니다."]
    if top_articles:
        lines.append(f"가장 먼저 확인할 기사는 '{top_articles[0]['title'] or '제목 없음'}'입니다.")
    if negative_rate >= 25:
        lines.append(f"부정 기사 비중이 {negative_rate}%로 높아 이슈 대응 메시지 점검이 필요합니다.")
    elif negative_rate:
        lines.append(f"부정 기사 비중은 {negative_rate}%로 관리 가능한 수준입니다.")
    else:
        lines.append("현재 뚜렷한 부정 기사 신호는 낮습니다.")
    if promotion_rate >= 20:
        lines.append(f"홍보성 기사 비중이 {promotion_rate}%입니다. 자연 노출과 유료/홍보 노출을 분리해 보고하세요.")
    if social_total:
        lines.append(f"SNS 최근 7일 신호는 {social_total}건이며 부정 힌트 비중은 {social_negative_rate}%입니다.")
    return lines


def _style_sheet(ws) -> None:
    ws.sheet_view.showGridLines = False
    thin = Side(style="thin", color=LINE)
    for row in ws.iter_rows():
        for cell in row:
            cell.border = Border(bottom=thin)
            cell.alignment = Alignment(vertical="top", wrap_text=True)


def _write_table(ws, start_row: int, start_col: int, title: str, headers: list[str], rows: list[tuple]) -> int:
    ws.cell(start_row, start_col, title).font = Font(bold=True, size=12, color=BLUE_DARK)
    header_row = start_row + 1
    for idx, header in enumerate(headers, start=start_col):
        cell = ws.cell(header_row, idx, header)
        cell.fill = PatternFill("solid", fgColor=BLUE_SOFT)
        cell.font = Font(bold=True, color=BLUE_DARK)
        cell.alignment = Alignment(horizontal="center")

    for row_idx, row in enumerate(rows or [("데이터 없음", 0)], start=header_row + 1):
        for col_idx, value in enumerate(row, start=start_col):
            ws.cell(row_idx, col_idx, value)
    return header_row + max(len(rows), 1)


def _add_bar_chart(ws, min_col: int, min_row: int, max_row: int, anchor: str, title: str) -> None:
    if max_row <= min_row:
        return
    chart = BarChart()
    chart.title = title
    chart.height = 7
    chart.width = 12
    data = Reference(ws, min_col=min_col + 1, min_row=min_row, max_row=max_row)
    cats = Reference(ws, min_col=min_col, min_row=min_row + 1, max_row=max_row)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.legend = None
    ws.add_chart(chart, anchor)


def _add_line_chart(ws, min_col: int, min_row: int, max_row: int, anchor: str, title: str) -> None:
    if max_row <= min_row:
        return
    chart = LineChart()
    chart.title = title
    chart.height = 7
    chart.width = 12
    data = Reference(ws, min_col=min_col + 1, min_row=min_row, max_row=max_row)
    cats = Reference(ws, min_col=min_col, min_row=min_row + 1, max_row=max_row)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.legend = None
    ws.add_chart(chart, anchor)


def _build_excel(rows, keyword_name: str | None = None, social_rows: list[dict] | None = None) -> Workbook:
    rows = list(rows)
    context = _report_context(rows, keyword_name, social_rows)
    wb = Workbook()

    summary_ws = wb.active
    summary_ws.title = "보고서 요약"
    summary_ws["A1"] = "AI 뉴스 인텔리전스 리포트"
    summary_ws["A1"].font = Font(bold=True, size=20, color=BLUE_DARK)
    summary_ws["A2"] = f"생성 시각: {context['generated_at']}"
    summary_ws["A3"] = f"키워드: {keyword_name or '전체 키워드'}"

    metrics = [
        ("전체 기사", context["total_count"]),
        ("AI 요약 완료", context["summary_count"]),
        ("중요도 산정", context["scored_count"]),
        ("평균 중요도", context["avg_score"] if context["avg_score"] is not None else "-"),
        ("부정 비중", f"{context['negative_rate']}%"),
        ("홍보성 비중", f"{context['promotion_rate']}%"),
        ("SNS 언급", context["social_total"]),
        ("SNS 부정 힌트", f"{context['social_negative_rate']}%"),
    ]
    for idx, (label, value) in enumerate(metrics, start=1):
        col = ((idx - 1) % 4) * 2 + 1
        row = 5 if idx <= 4 else 8
        summary_ws.cell(row, col, label).font = Font(bold=True, color=MUTED)
        summary_ws.cell(row + 1, col, value).font = Font(bold=True, size=16, color=BLUE)

    summary_ws["A11"] = "Executive Summary"
    summary_ws["A11"].font = Font(bold=True, size=13, color=BLUE_DARK)
    for row_idx, line in enumerate(context["executive_summary"], start=12):
        summary_ws.cell(row_idx, 1, f"- {line}")

    for col in range(1, 9):
        summary_ws.column_dimensions[summary_ws.cell(1, col).column_letter].width = 18

    chart_ws = wb.create_sheet("그래프")
    keyword_end = _write_table(chart_ws, 1, 1, "키워드별 기사 수", ["키워드", "기사 수"], context["keyword_counts"])
    sentiment_end = _write_table(chart_ws, 1, 5, "감성 분포", ["감성", "건수"], context["sentiment_counts"])
    promotion_end = _write_table(chart_ws, 16, 1, "홍보성 분포", ["구분", "건수"], context["promotion_counts"])
    daily_end = _write_table(chart_ws, 16, 5, "일자별 기사 추이", ["날짜", "기사 수"], context["daily_counts"][-30:])
    social_end = _write_table(chart_ws, 31, 1, "SNS 플랫폼별 언급", ["플랫폼", "언급 수"], context["social_source_counts"])
    _add_bar_chart(chart_ws, 1, 2, keyword_end, "H1", "키워드별 기사 수")
    _add_bar_chart(chart_ws, 5, 2, sentiment_end, "H16", "감성 분포")
    _add_bar_chart(chart_ws, 1, 17, promotion_end, "H31", "홍보성 분포")
    _add_line_chart(chart_ws, 5, 17, daily_end, "A46", "일자별 기사 추이")
    _add_bar_chart(chart_ws, 1, 32, social_end, "H46", "SNS 플랫폼별 언급")
    for col in range(1, 12):
        chart_ws.column_dimensions[chart_ws.cell(1, col).column_letter].width = 16

    priority_ws = wb.create_sheet("우선 확인 기사")
    priority_headers = ["순위", "제목", "출처", "게시 일시", "감성", "홍보성", "중요도", "AI 요약", "원문 URL"]
    priority_ws.append(priority_headers)
    for idx, row in enumerate(context["top_articles"], start=1):
        priority_ws.append([
            idx,
            row["title"] or "",
            row["publisher"] or "",
            _fmt_dt(row["published_at"]),
            _sentiment_key(row["sentiment"]),
            _promotion_label(row["is_promotion"]),
            _score_value(row) or "",
            row["summary_text"] or "",
            row["url"] or "",
        ])
    for idx, width in enumerate([8, 56, 18, 18, 12, 12, 10, 66, 52], start=1):
        priority_ws.column_dimensions[priority_ws.cell(1, idx).column_letter].width = width

    article_ws = wb.create_sheet("기사 상세")
    article_ws.append(ARTICLE_HEADERS)
    for row in rows:
        article_ws.append([
            row["id"],
            row["title"] or "",
            row["publisher"] or "",
            _fmt_dt(row["published_at"]),
            row["keywords"] or "",
            _sentiment_key(row["sentiment"]),
            _promotion_label(row["is_promotion"]),
            _score_value(row) or "",
            row["importance_reason"] or "",
            row["summary_text"] or "",
            row["url"] or "",
            row["language"] or "",
            _fmt_dt(row["created_at"]),
        ])
    for idx, width in enumerate(ARTICLE_WIDTHS, start=1):
        article_ws.column_dimensions[article_ws.cell(1, idx).column_letter].width = width
    article_ws.freeze_panes = "A2"
    article_ws.auto_filter.ref = article_ws.dimensions
    if article_ws.max_row >= 2:
        article_ws.conditional_formatting.add(
            f"H2:H{article_ws.max_row}",
            ColorScaleRule(start_type="num", start_value=0, start_color="FFFFFF", end_type="num", end_value=100, end_color="93C5FD"),
        )

    sns_ws = wb.create_sheet("SNS 신호")
    sns_ws.append(["키워드", "플랫폼", "언급 수", "긍정 힌트", "부정 힌트", "수집 시각"])
    for row in social_rows or []:
        sns_ws.append([
            row.get("keyword_text") or "",
            row.get("source") or "",
            row.get("mention_count") or 0,
            row.get("positive_hint_count") or 0,
            row.get("negative_hint_count") or 0,
            _fmt_dt(row.get("sampled_at")),
        ])
    for idx, width in enumerate([24, 16, 12, 12, 12, 20], start=1):
        sns_ws.column_dimensions[sns_ws.cell(1, idx).column_letter].width = width
    sns_ws.auto_filter.ref = sns_ws.dimensions

    for ws in wb.worksheets:
        header_row = 1
        for cell in ws[header_row]:
            if cell.value:
                cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        _style_sheet(ws)

    return wb


def _html_bar_chart(title: str, rows: list[tuple[str, int]], color: str = "#60a5fa") -> str:
    data = rows[:8] or [("데이터 없음", 0)]
    max_value = max([value for _, value in data] + [1])
    bar_rows = []
    for label, value in data:
        width = max(2, int((value / max_value) * 100)) if max_value else 2
        bar_rows.append(
            f"""
            <tr>
              <td style="width:150px;padding:7px 8px;color:#334155;font-size:12px;">{escape(str(label)[:24])}</td>
              <td style="padding:7px 8px;">
                <div style="background:#eff6ff;border-radius:999px;height:16px;overflow:hidden;">
                  <div style="background:{color};width:{width}%;height:16px;border-radius:999px;"></div>
                </div>
              </td>
              <td style="width:52px;padding:7px 8px;text-align:right;font-weight:700;color:#172033;">{value}</td>
            </tr>
            """
        )
    return f"""
    <div style="border:1px solid #dbeafe;border-radius:8px;padding:14px;margin-bottom:12px;">
      <h3 style="margin:0 0 8px;font-size:16px;color:#1e3a8a;">{escape(title)}</h3>
      <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">{''.join(bar_rows)}</table>
    </div>
    """


def _build_email_html(context: dict) -> str:
    keyword_label = escape(context["keyword_name"] or "전체 키워드")
    executive_items = "".join(f"<li>{escape(line)}</li>" for line in context["executive_summary"])
    top_rows = "".join(
        f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #dbeafe;">{idx}</td>
          <td style="padding:10px;border-bottom:1px solid #dbeafe;"><strong>{escape(row['title'] or '제목 없음')}</strong><br>
            <span style="color:#64748b;">{escape(row['publisher'] or '출처 없음')} · {_fmt_dt(row['published_at'])}</span>
            <p style="margin:8px 0 0;color:#334155;line-height:1.5;">{escape((row['summary_text'] or '요약문이 아직 없습니다.')[:420])}</p>
          </td>
          <td style="padding:10px;border-bottom:1px solid #dbeafe;text-align:right;font-weight:700;">{(_score_value(row) or 0):.1f}</td>
        </tr>
        """
        for idx, row in enumerate(context["top_articles"][:5], start=1)
    ) or '<tr><td colspan="3" style="padding:14px;color:#64748b;">중요도 산정 완료 기사가 아직 없습니다.</td></tr>'

    return f"""
    <html>
      <body style="margin:0;background:#f8fbff;font-family:Arial,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#172033;">
        <div style="max-width:860px;margin:0 auto;padding:28px;">
          <div style="background:linear-gradient(135deg,#eff6ff,#ffffff);border:1px solid #dbeafe;border-radius:10px;padding:24px;">
            <div style="font-size:13px;color:#64748b;">{escape(context['generated_at'])}</div>
            <h1 style="margin:8px 0 0;font-size:26px;color:#1e3a8a;">AI 뉴스 인텔리전스 리포트</h1>
            <p style="margin:8px 0 0;color:#334155;">{keyword_label} 기준 기사, AI 분석, SNS 신호를 정리했습니다.</p>
          </div>

          <table width="100%" cellspacing="0" cellpadding="0" style="margin:18px 0;background:white;border:1px solid #dbeafe;border-radius:10px;overflow:hidden;">
            <tr>
              <td style="padding:18px;"><div style="color:#64748b;font-size:12px;">전체 기사</div><strong style="font-size:24px;">{context['total_count']}</strong></td>
              <td style="padding:18px;"><div style="color:#64748b;font-size:12px;">부정 비중</div><strong style="font-size:24px;">{context['negative_rate']}%</strong></td>
              <td style="padding:18px;"><div style="color:#64748b;font-size:12px;">홍보성 비중</div><strong style="font-size:24px;">{context['promotion_rate']}%</strong></td>
              <td style="padding:18px;"><div style="color:#64748b;font-size:12px;">SNS 언급</div><strong style="font-size:24px;">{context['social_total']}</strong></td>
            </tr>
          </table>

          <div style="background:white;border:1px solid #dbeafe;border-radius:10px;padding:16px;margin-bottom:18px;">
            <h2 style="margin:0 0 12px;font-size:18px;">Executive Summary</h2>
            <ul style="margin:0;padding-left:20px;color:#334155;line-height:1.7;">{executive_items}</ul>
          </div>

          <div style="background:white;border:1px solid #dbeafe;border-radius:10px;padding:16px;margin-bottom:18px;">
            <h2 style="margin:0 0 12px;font-size:18px;">그래프 요약</h2>
            {_html_bar_chart("감성 분포", context["sentiment_counts"], "#60a5fa")}
            {_html_bar_chart("홍보성 분포", context["promotion_counts"], "#f59e0b")}
            {_html_bar_chart("SNS 플랫폼별 언급", context["social_source_counts"], "#22d3ee")}
          </div>

          <div style="background:white;border:1px solid #dbeafe;border-radius:10px;padding:16px;">
            <h2 style="margin:0 0 12px;font-size:18px;">우선 확인 기사</h2>
            <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
              <thead><tr style="background:#eff6ff;"><th align="left" style="padding:10px;">#</th><th align="left" style="padding:10px;">기사 및 요약</th><th align="right" style="padding:10px;">중요도</th></tr></thead>
              <tbody>{top_rows}</tbody>
            </table>
          </div>
        </div>
      </body>
    </html>
    """


def _build_email_text(context: dict) -> str:
    top_lines = [
        f"{idx}. {row['title'] or '제목 없음'} / 중요도 {(_score_value(row) or 0):.1f}"
        for idx, row in enumerate(context["top_articles"][:5], start=1)
    ]
    return "\n".join([
        "AI 뉴스 인텔리전스 리포트",
        f"생성 시각: {context['generated_at']}",
        f"키워드: {context['keyword_name'] or '전체 키워드'}",
        "",
        "Executive Summary",
        *[f"- {line}" for line in context["executive_summary"]],
        "",
        f"전체 기사: {context['total_count']}",
        f"부정 비중: {context['negative_rate']}%",
        f"홍보성 비중: {context['promotion_rate']}%",
        f"SNS 언급: {context['social_total']}",
        "",
        "우선 확인 기사",
        *(top_lines or ["중요도 산정 완료 기사가 아직 없습니다."]),
        "",
        "상세 내용은 첨부된 Excel 보고서에서 확인해 주세요.",
    ])


async def _report_rows(db: AsyncSession, current_user: User, keyword_id: int | None):
    stmt = _build_query(current_user, keyword_id=keyword_id)
    result = await db.execute(stmt)
    return result.mappings().all()


@router.get("/daily")
async def download_daily_report(
    keyword_id: int | None = Query(None, description="특정 키워드 필터"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    keyword_name = await _keyword_name(db, current_user, keyword_id)
    rows = await _report_rows(db, current_user, keyword_id)
    social_rows = await _get_social_report_rows(db, current_user, keyword_id=keyword_id)

    wb = _build_excel(rows, keyword_name=keyword_name, social_rows=social_rows)
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
    keyword_name = body.keyword_name or await _keyword_name(db, current_user, body.keyword_id)
    rows = await _report_rows(db, current_user, body.keyword_id)
    social_rows = await _get_social_report_rows(db, current_user, keyword_id=body.keyword_id)

    wb = _build_excel(rows, keyword_name=keyword_name, social_rows=social_rows)
    stream = io.BytesIO()
    wb.save(stream)
    excel_bytes = stream.getvalue()

    context = _report_context(rows, keyword_name, social_rows)
    email_service = EmailService()
    email_service.send_daily_report(
        to_emails=body.to_emails,
        excel_bytes=excel_bytes,
        keyword_name=keyword_name,
        html_body=_build_email_html(context),
        text_body=_build_email_text(context),
    )

    return success_response(
        request=request,
        data={
            "sent_to": body.to_emails,
            "article_count": len(rows),
            "message": f"{len(body.to_emails)}명에게 데일리 리포트를 발송했습니다.",
        },
    )
