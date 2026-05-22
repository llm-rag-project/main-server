from api.client import api_get, api_post


def create_crawl_run(keyword_ids: list[int] | None = None, force: bool = False):
    payload = {
        "keyword_ids": keyword_ids or [],
        "force": force,
    }
    return api_post("/crawl-runs", payload)


def get_pending_analysis_count() -> int:
    """미분석 기사 수 조회"""
    result = api_get("/crawl-runs/analysis/pending")
    return result.get("pending_count", 0)


def run_analysis(job_id: str | None = None):
    """미분석 기사에 대해 AI 감성/홍보성 분석 수동 실행"""
    return api_post("/crawl-runs/analysis", {"job_id": job_id})


def get_crawl_runs(page=1, size=20, status=None, keyword_id=None):
    params = {
        "page": page,
        "size": size,
    }
    if status:
        params["status"] = status
    if keyword_id is not None:
        params["keyword_id"] = keyword_id

    return api_get("/crawl-runs", params=params)