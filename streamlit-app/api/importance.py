from api.client import api_post


def submit_scoring_feedback(
    article_id: int,
    original_score: int,
    user_score: int,
    reason: str,
):
    return api_post("/importance/feedback", {
        "article_id": article_id,
        "original_score": original_score,
        "user_score": user_score,
        "reason": reason,
    })
