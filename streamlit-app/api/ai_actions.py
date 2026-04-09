# api/ai_actions.py
from api.client import api_post


def request_article_summary(article_id: int):
    return api_post("/ai/summary", {
        "article_id": article_id,
    })


def request_articles_scoring(keyword_id: int, article_ids: list[int]):
    return api_post("/ai/scoring", {
        "keyword_id": keyword_id,
        "article_ids": article_ids,
    })