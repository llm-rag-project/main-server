import asyncio
import json
import re
from pathlib import Path
from collections import Counter
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.api.v1.reports import (
    _build_dongguk_preview_result,
    _article_item_to_dongguk,
    _dongguk_articles_for_keyword_date,
    _dongguk_mail_section_policy,
    _dongguk_mail_subject,
    _dongguk_report_window,
)
import app.schemas.articles
from app.services.article_service import ArticleService
from app.db.session import AsyncSessionLocal
from app.models.keyword import Keyword
from app.models.user import User
from sqlalchemy import select


DATES = ["2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17", "2026-07-20", "2026-07-21"]
OUTPUT_PATH = Path("/code/exports/dongguk_sheet_rows_latest.json")

SOURCE_BY_DOMAIN = {
    "basketkorea.com": "바스켓코리아",
    "biz.chosun.com": "조선비즈",
    "chosun.com": "조선일보",
    "dhnews.co.kr": "대학저널",
    "ebs.co.kr": "EBS 뉴스",
    "news.ebs.co.kr": "EBS 뉴스",
    "geconomy.co.kr": "지이코노미",
    "gosiweek.com": "피앤피뉴스",
    "hangyo.com": "한국교육신문",
    "hankyung.com": "한경잡앤조이",
    "hellot.net": "헬로티",
    "kgnews.co.kr": "경기신문",
    "kpinews.kr": "KPI뉴스",
    "m.skyedaily.com": "스카이데일리",
    "m.sports.naver.com": "점프볼",
    "magazine.hankyung.com": "한경잡앤조이",
    "megaeconomy.co.kr": "메가경제",
    "mtn.co.kr": "MTN 머니투데이방송",
    "news.mtn.co.kr": "MTN 머니투데이방송",
    "news.tvchosun.com": "TV조선",
    "socialvalue.kr": "소셜밸류",
    "swtvnews.com": "SWTV",
    "taxtimes.co.kr": "한국세정신문",
    "tfmedia.co.kr": "조세금융신문",
    "wsobi.com": "여성소비자신문",
}


def section_label(section):
    if section in {"dongguk_core", "dongguk_media", "foundation"}:
        return "동국대 [법인/건학위]"
    if section == "education":
        return "대학 [교육]"
    if section == "buddhism":
        return "불교 [종단]"
    return section or "미분류"

def source_label(source, url):
    source = (source or "").strip()
    if source and source.lower() != "unknown":
        return source

    parsed = urlparse(url or "")
    host = parsed.netloc.lower().removeprefix("www.")
    if not host:
        return source or ""
    if host in SOURCE_BY_DOMAIN:
        return SOURCE_BY_DOMAIN[host]

    parts = host.split(".")
    registrable = ".".join(parts[-2:]) if len(parts) >= 2 else host
    return SOURCE_BY_DOMAIN.get(registrable, source or host)


def collection_source_label(value):
    normalized = (value or "").strip().lower()
    if normalized == "google_rss":
        return "구글RSS"
    if normalized == "naver":
        return "네이버"
    if normalized in {"dongguk_official", "official"}:
        return "동국대 자체"
    return ""


def real_article_links(article):
    links = article.links or ([article.url] if article.url else [])
    return [
        str(link).strip()
        for link in dict.fromkeys(links)
        if str(link).strip().lower().startswith(("http://", "https://"))
        and not re.search(r"//(?:www\.)?example\.com(?:/|$)", str(link), re.I)
    ]


def canonical_article_url(value=""):
    raw = str(value or "").strip()
    try:
        parsed = urlparse(raw)
        host = parsed.netloc.lower()
        host = re.sub(r"^(?:www\.|m\.)", "", host)
        path = re.sub(r"/+", "/", parsed.path or "/")
        path = re.sub(r"/(?:amp|mobile)/", "/", path, flags=re.I)
        path = re.sub(r"view_amp(?=\.)", "view", path, flags=re.I)
        path = path.rstrip("/") or "/"
        params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        stable_keys = ["arcid", "idxno", "no", "article_id", "articleid", "aid", "id"]
        stable_key = next((key for key in stable_keys if params.get(key)), None)
        if stable_key:
            query = urlencode({stable_key: params[stable_key]})
        else:
            drop_keys = {"cp", "from", "gclid", "fbclid", "medium", "ncid", "ocid", "ref", "source"}
            query = urlencode(
                sorted(
                    (key, value)
                    for key, value in params.items()
                    if not key.lower().startswith("utm_") and key.lower() not in drop_keys
                )
            )
        return urlunparse(("https", host, path, "", query, "")).rstrip("/")
    except Exception:
        return raw.split("#", 1)[0].rstrip("/").lower()


def normalized_article_title(article):
    source = (article.source or "").strip()
    title = re.sub(r"<[^>]+>", " ", article.title or "")
    if source:
        title = re.sub(rf"\s*[-|]\s*{re.escape(source)}\s*$", "", title, flags=re.I)
    title = re.sub(r"\s*[-|]\s*(?:네이버\s*뉴스|구글\s*뉴스|뉴스)\s*$", "", title, flags=re.I)
    return re.sub(r"[^0-9a-z가-힣]+", "", title.lower())


def article_identity(article):
    links = real_article_links(article)
    if links:
        return f"url:{canonical_article_url(links[0])}"
    title = normalized_article_title(article)
    source = re.sub(r"\s+", " ", article.source or "").strip().lower()
    if title and source:
        return f"title-source:{title}|{source}"
    if article.id is not None:
        return f"id:{article.id}"
    return f"title:{(article.title or '').strip().lower()}|{source}"


def preview_item_identity(item):
    url = item.get("url") or ((item.get("links") or [""])[0])
    if url:
        return f"url:{canonical_article_url(url)}"
    title = normalized_article_title(type("ArticleLike", (), {
        "title": item.get("title") or "",
        "source": item.get("source") or "",
    })())
    source = re.sub(r"\s+", " ", item.get("source") or "").strip().lower()
    if title and source:
        return f"title-source:{title}|{source}"
    article_id = item.get("id")
    if article_id is not None:
        return f"id:{article_id}"
    return f"title:{(item.get('title') or '').strip().lower()}|{source}"


async def dashboard_articles_for_keyword_date(db, *, user_id, keyword_id, mail_date, send_time):
    window_start, window_end = _dongguk_report_window(mail_date, send_time)
    service = ArticleService(db)
    published_query = app.schemas.articles.ArticleListQuery(
        page=1,
        size=100,
        keyword_id=keyword_id,
        sort=app.schemas.articles.ArticleSort.importance_desc,
        from_at=window_start,
        to_at=window_end,
    )
    published_page_items, _ = await service.get_article_list(user_id=user_id, query=published_query)
    published_articles = [_article_item_to_dongguk(item) for item in published_page_items]

    matched_query = app.schemas.articles.ArticleListQuery(
        page=1,
        size=100,
        keyword_id=keyword_id,
        sort=app.schemas.articles.ArticleSort.importance_desc,
        matched_from=mail_date,
        matched_to=mail_date,
    )
    matched_page_items, _ = await service.get_article_list(user_id=user_id, query=matched_query)
    matched_articles = [_article_item_to_dongguk(item) for item in matched_page_items]

    by_key = {}
    for article in [*published_articles, *matched_articles]:
        key = article_identity(article)
        if key not in by_key:
            by_key[key] = article

    return sorted(by_key.values(), key=lambda article: article.score or 0, reverse=True)


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Keyword, User)
            .join(User, User.id == Keyword.user_id)
            .where(Keyword.keyword_text.ilike("%동국%"))
            .order_by(Keyword.id.asc())
            .limit(1)
        )
        row = result.first()
        if not row:
            raise RuntimeError("동국 키워드를 찾지 못했습니다.")
        keyword, user = row
        out = {"keyword_id": keyword.id, "user_id": user.id, "dates": {}}
        for mail_date in DATES:
            articles = await dashboard_articles_for_keyword_date(
                db,
                user_id=user.id,
                keyword_id=keyword.id,
                mail_date=mail_date,
                send_time=keyword.email_send_time,
            )
            try:
                preview = await _build_dongguk_preview_result(
                    db=db,
                    current_user=user,
                    subject=_dongguk_mail_subject(mail_date),
                    mail_date=mail_date,
                    articles=articles,
                    exclude_similar_sent=False,
                    keyword_id=keyword.id,
                    priority_criteria=keyword.importance_criteria,
                )
            except Exception as exc:
                included_articles, excluded_articles = _dongguk_mail_section_policy(
                    articles,
                    [],
                    articles,
                    mail_date,
                )
                preview = {
                    "articles": [article.model_dump() for article in included_articles],
                    "excluded_articles": [article.model_dump() for article in excluded_articles],
                    "article_count": len(included_articles),
                    "excluded_count": len(excluded_articles),
                    "editor_used": False,
                    "export_fallback_reason": str(exc),
                }
            included_ids = {item.get("id") for item in preview.get("articles") or [] if item.get("id") is not None}
            included_keys = {
                preview_item_identity(item)
                for item in preview.get("articles") or []
            }
            rows = []
            for idx, item in enumerate(preview.get("articles") or [], start=1):
                rows.append({
                    "기준일": mail_date,
                    "포함여부": "메일 포함",
                    "순번": idx,
                    "섹션": section_label(item.get("section")),
                    "수집 출처": collection_source_label(item.get("collection_source")),
                    "제목": item.get("title"),
                    "발행일시": item.get("published_at"),
                    "URL": item.get("url") or ((item.get("links") or [""])[0]),
                    "수집풀": item.get("section") or "",
                })
            excluded_index = len(rows) + 1
            for item in articles:
                key = article_identity(item)
                if (item.id is not None and item.id in included_ids) or key in included_keys:
                    continue
                rows.append({
                    "기준일": mail_date,
                    "포함여부": "메일 제외",
                    "순번": excluded_index,
                    "섹션": section_label(item.section),
                    "수집 출처": collection_source_label(item.collection_source),
                    "제목": item.title,
                    "발행일시": item.published_at,
                    "URL": item.url or ((item.links or [""])[0]),
                    "수집풀": item.section or "",
                })
                excluded_index += 1
            out["dates"][mail_date] = {
                "candidate_count": len(articles),
                "included_count": len(preview.get("articles") or []),
                "included_sections": dict(Counter(row["섹션"] for row in rows if row["포함여부"] == "메일 포함")),
                "candidate_sections": dict(Counter(section_label(item.section) for item in articles)),
                "rows": rows,
            }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(out, ensure_ascii=False, default=str), encoding="utf-8")
        print(json.dumps({
            "output_path": str(OUTPUT_PATH),
            "keyword_id": out["keyword_id"],
            "summary": {
                mail_date: {
                    "candidate_count": data["candidate_count"],
                    "included_count": data["included_count"],
                    "included_sections": data["included_sections"],
                    "candidate_sections": data["candidate_sections"],
                }
                for mail_date, data in out["dates"].items()
            },
        }, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
