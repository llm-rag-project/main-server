import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.crawl_run_service import CrawlRunService


class CrawlKeywordRelevanceTests(unittest.TestCase):
    def setUp(self):
        self.service = CrawlRunService(db=None, transnews_client=None)

    def test_accepts_keyword_in_article_metadata(self):
        item = {
            "title": "대학 연구 성과 발표",
            "summary": "",
            "content": "본문에는 학교 이름이 직접 나오지 않습니다.",
            "publisher": "동국대학교",
            "annotations": ["연구", "대학"],
        }

        self.assertTrue(
            self.service._contains_keyword(keyword_text="동국대학교", item=item)
        )

    def test_accepts_keyword_in_annotations(self):
        item = {
            "title": "지역 교육 행사 개최",
            "summary": "",
            "content": "행사 내용 안내",
            "annotations": ["동국대", "교육"],
        }

        self.assertTrue(
            self.service._contains_keyword(keyword_text="동국대학교", item=item)
        )

    def test_search_description_avoids_redundant_body_crawl(self):
        self.assertTrue(
            self.service._has_usable_text(
                {"content": "", "description": "검색 결과에서 확보한 기사 요약"}
            )
        )

    def test_empty_search_metadata_still_needs_body_crawl(self):
        self.assertFalse(
            self.service._has_usable_text(
                {"content": "", "description": " ", "summary": None}
            )
        )

    def test_crawled_publisher_can_make_candidate_relevant(self):
        item = {
            "title": "연구 성과 발표",
            "description": "새로운 연구 성과를 소개합니다.",
        }
        self.service._merge_crawled_metadata(
            item,
            {"publisher": "동국대학교", "author": "홍보실"},
        )

        self.assertTrue(
            self.service._contains_keyword(keyword_text="동국대학교", item=item)
        )

    def test_rejects_single_incidental_body_mention(self):
        item = {
            "title": "전국 대학 종합 소식",
            "summary": "",
            "content": "여러 대학 가운데 동국대도 한 차례 언급됐습니다.",
        }

        self.assertFalse(
            self.service._contains_keyword(keyword_text="동국대학교", item=item)
        )


    def test_audit_separates_education_and_buddhism_section_pools(self):
        self.assertEqual(
            self.service._audit_source_name(
                {"source_type": "section_pool", "section": "education"}
            ),
            "section_pool_education",
        )
        self.assertEqual(
            self.service._audit_source_name(
                {"source_type": "section_pool", "section": "buddhism"}
            ),
            "section_pool_buddhism",
        )


class CrawlRelevanceEnrichmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_canonical_url_is_enriched_once(self):
        crawl_article = AsyncMock(
            return_value={"data": {"publisher": "동국대학교"}}
        )
        service = CrawlRunService(
            db=None,
            transnews_client=SimpleNamespace(crawl_article=crawl_article),
        )
        items = [
            {
                "title": "연구 성과 발표",
                "url": "https://example.com/article?id=1&utm_source=naver",
                "published": "2026-07-30T09:00:00+09:00",
            },
            {
                "title": "연구 성과 후속 보도",
                "url": "https://example.com/article?id=1",
                "published": "2026-07-30T09:00:00+09:00",
            },
        ]

        await service._enrich_relevance_candidates(
            items=items,
            keyword_text="동국대학교",
            window_start=datetime(2026, 7, 30, tzinfo=timezone.utc),
            window_end=datetime(2026, 7, 31, tzinfo=timezone.utc),
        )

        crawl_article.assert_awaited_once()
        self.assertEqual([item["publisher"] for item in items], ["동국대학교"] * 2)


if __name__ == "__main__":
    unittest.main()
