from api.client import api_get, api_post


def set_user_score(article_id: int, score: float, reason: str | None = None):
    return api_post("/importance/my-score", {
        "article_id": article_id,
        "score": score,
        "reason": reason,
    })


def get_user_preference():
    return api_get("/importance/my-preference")
