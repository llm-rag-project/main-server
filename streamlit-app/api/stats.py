from api.client import api_get


def get_article_stats(days: int = 7):
    """DB 기반 - 키워드별/날짜별 수집 기사 수"""
    return api_get("/stats/articles", params={"days": days})


def get_search_volume():
    """크롤링 서버 기반 - 키워드별 실시간 검색량"""
    return api_get("/stats/search-volume")