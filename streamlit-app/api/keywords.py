import os
from dotenv import load_dotenv

from api.client import api_delete, api_get, api_patch, api_post
from api.crawl_runs import create_crawl_run

load_dotenv()
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "ko")


def get_keywords(page=1, size=100, is_active=None, language=None, q=None):
    params = {
        "page": page,
        "size": size,
    }
    if is_active is not None:
        params["is_active"] = is_active
    if language:
        params["language"] = language
    if q:
        params["q"] = q

    result = api_get("/keywords", params=params)

    items = result.get("items", []) if isinstance(result, dict) else []
    page_info = result.get("page_info") if isinstance(result, dict) else None
    return items, page_info


def create_keyword(keyword: str, language: str = DEFAULT_LANGUAGE):
    payload = {
        "keyword": keyword,
        "language": language,
    }
    return api_post("/keywords", payload)


def create_keyword_and_crawl(keyword: str, language: str = DEFAULT_LANGUAGE):
    created = create_keyword(keyword=keyword, language=language)

    keyword_data = created.get("keyword", {})
    keyword_id = keyword_data.get("id")
    if not keyword_id:
        raise ValueError(f"키워드 생성 응답에 id가 없습니다: {created}")

    crawl_result = created.get("crawl_result")
    print("crawl_result =", crawl_result)

    return {
        "keyword": keyword_data,
        "crawl_run": crawl_result,
    }


def batch_create_keywords(keywords: list[str], language: str = DEFAULT_LANGUAGE):
    payload = {
        "keywords": keywords,
        "language": language,
    }
    return api_post("/keywords/batch", payload)


def update_keyword_active(keyword_id: int, is_active: bool):
    payload = {"is_active": is_active}
    return api_patch(f"/keywords/{keyword_id}", payload)


def delete_keyword(keyword_id: int):
    return api_delete(f"/keywords/{keyword_id}")