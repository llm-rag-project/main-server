import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.crawl_run_service import CrawlRunService


KST = ZoneInfo("Asia/Seoul")


class CrawlWindowTests(unittest.TestCase):
    def setUp(self):
        self.service = CrawlRunService.__new__(CrawlRunService)
        self.start_at = datetime(2026, 7, 27, 8, 30, tzinfo=KST)
        self.end_at = datetime(2026, 7, 28, 8, 30, tzinfo=KST)

    def test_section_pool_article_inside_window_is_included(self):
        item = {
            "published_at": "2026-07-27T09:00:00+09:00",
            "source_type": "section_pool",
            "section": "education",
        }

        self.assertTrue(
            self.service._is_in_crawl_window(item, self.start_at, self.end_at)
        )

    def test_section_pool_article_before_window_is_not_counted(self):
        item = {
            "published_at": "2026-07-26T09:00:00+09:00",
            "source_type": "section_pool",
            "section": "buddhism",
        }

        self.assertFalse(
            self.service._is_in_crawl_window(item, self.start_at, self.end_at)
        )

    def test_regular_article_on_end_boundary_is_included(self):
        item = {"published_at": "2026-07-28T08:30:00+09:00"}

        self.assertTrue(
            self.service._is_in_crawl_window(item, self.start_at, self.end_at)
        )


if __name__ == "__main__":
    unittest.main()
