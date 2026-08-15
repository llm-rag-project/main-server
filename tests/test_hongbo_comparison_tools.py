from scripts.compare_hongbo_original_vs_ai import greedy_matches, score_pair
from scripts.extract_hongbo_original_mails import canonical_url, split_title_source


def test_canonical_url_removes_tracking_and_mobile_variants():
    assert canonical_url(
        "http://m.example.com/news/amp/articleView.html?idxno=123&utm_source=test"
    ) == "https://example.com/news/articleView.html?idxno=123"


def test_split_title_source_preserves_syndication_marker():
    title, source, syndicated = split_title_source("동국대 연구 성과 발표 [전자신문 외]")
    assert title == "동국대 연구 성과 발표"
    assert source == "전자신문"
    assert syndicated is True


def test_comparison_prefers_exact_url_over_similar_title():
    original = {
        "title": "세종대·동국대 지능IoT 공동학위 협약",
        "urls": ["https://example.com/article?id=10"],
    }
    exact = {
        "title": "표현이 다른 제목",
        "links": ["https://www.example.com/article?id=10&utm_source=news"],
    }
    similar = {"title": "세종대 동국대 지능 IoT 공동학위 운영 협약", "links": []}

    exact_score, exact_method = score_pair(original, exact)
    similar_score, _ = score_pair(original, similar)
    assert exact_method == "URL 일치"
    assert exact_score > similar_score


def test_greedy_matches_each_server_article_only_once():
    originals = [
        {"title": "동국대 기부금 전달", "urls": []},
        {"title": "동국대학교 기부금 전달 소식", "urls": []},
    ]
    server = [{"title": "동국대 기부금 전달", "links": []}]

    matches = greedy_matches(originals, server)
    assert len(matches) == 1
