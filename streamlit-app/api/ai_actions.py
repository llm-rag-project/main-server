from api.client import api_post


def request_article_summary(article_id: int):
    payload = {
        "article_id": article_id,
    }
    return api_post("/ai/summary", payload)


def request_articles_scoring(article_ids: list[int]):
    payload = {
        "article_ids": article_ids,
    }
    return api_post("/ai/scoring", payload)