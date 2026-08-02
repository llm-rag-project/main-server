import unittest
from types import SimpleNamespace

from app.services.crawl_scheduler_service import (
    AUTO_RETRY_MAX_ATTEMPTS,
    _dongguk_collection_needs_retry,
)


def source(
    name: str,
    *,
    status: str = "success",
    discovered: int = 0,
    stored: int = 0,
    duplicates: int = 0,
):
    return SimpleNamespace(
        source_name=name,
        status=status,
        discovered_count=discovered,
        stored_count=stored,
        duplicate_count=duplicates,
    )


class DonggukAutoRetryTests(unittest.TestCase):
    def test_retry_limit_is_three(self):
        self.assertEqual(AUTO_RETRY_MAX_ATTEMPTS, 3)

    def test_complete_three_section_result_does_not_retry(self):
        sources = [
            source("naver", discovered=10),
            source("section_pool_education", discovered=2),
            source("section_pool_buddhism", discovered=3),
        ]

        self.assertFalse(_dongguk_collection_needs_retry(sources))

    def test_optional_source_timeout_does_not_retry_when_other_sources_are_healthy(self):
        sources = [
            source("dongguk_official", status="timeout"),
            source("google_rss", discovered=4),
            source("section_pool_education", discovered=1),
            source("section_pool_buddhism", discovered=1),
        ]

        self.assertFalse(_dongguk_collection_needs_retry(sources))

    def test_missing_education_section_retries(self):
        sources = [
            source("naver", discovered=10),
            source("section_pool_buddhism", discovered=2),
        ]

        self.assertTrue(_dongguk_collection_needs_retry(sources))

    def test_successful_but_empty_section_retries(self):
        sources = [
            source("naver", discovered=10),
            source("section_pool_education", status="success"),
            source("section_pool_buddhism", discovered=2),
        ]

        self.assertTrue(_dongguk_collection_needs_retry(sources))

    def test_existing_duplicate_counts_as_a_usable_result(self):
        sources = [
            source("naver", duplicates=5),
            source("section_pool_education", duplicates=1),
            source("section_pool_buddhism", duplicates=2),
        ]

        self.assertFalse(_dongguk_collection_needs_retry(sources))


if __name__ == "__main__":
    unittest.main()
