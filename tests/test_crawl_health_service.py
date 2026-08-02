import unittest
from datetime import datetime, timezone

from app.models.crawl_run_source import CrawlRunSource
from app.services.crawl_health_service import reconciliation_delta


class CrawlHealthReconciliationTests(unittest.TestCase):
    def test_reconciliation_is_exact_when_every_candidate_has_outcome(self):
        source = CrawlRunSource(
            crawl_run_id=1,
            keyword_id=1,
            source_name="merged_pipeline",
            trigger_type="manual",
            status="success",
            window_start=datetime.now(timezone.utc),
            window_end=datetime.now(timezone.utc),
            discovered_count=10,
            stored_count=3,
            duplicate_count=2,
            rejected_date_count=1,
            rejected_relevance_count=3,
            failed_count=1,
            diagnostics={},
        )

        self.assertEqual(reconciliation_delta(source), 0)

    def test_reconciliation_exposes_unclassified_candidates(self):
        source = CrawlRunSource(
            crawl_run_id=1,
            keyword_id=1,
            source_name="merged_pipeline",
            trigger_type="manual",
            status="partial",
            window_start=datetime.now(timezone.utc),
            window_end=datetime.now(timezone.utc),
            discovered_count=10,
            stored_count=4,
            duplicate_count=2,
            rejected_date_count=1,
            rejected_relevance_count=1,
            failed_count=0,
            diagnostics={},
        )

        self.assertEqual(reconciliation_delta(source), 2)
