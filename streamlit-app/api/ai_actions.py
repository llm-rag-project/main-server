# api/ai_actions.py
from api.client import api_post


def request_article_summary(article_id: int, job_id: str | None = None):
    payload: dict = {"article_id": article_id}
    if job_id:
        payload["job_id"] = job_id
    return api_post("/ai/summary", payload)


def request_articles_scoring(keyword_id: int, job_id: str | None = None):
    payload: dict = {"keyword_id": keyword_id}
    if job_id:
        payload["job_id"] = job_id
    return api_post("/importance/run", payload)