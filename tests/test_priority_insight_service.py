import unittest
from datetime import date

from app.services.priority_insight_service import (
    build_draft_action_events,
    fallback_priority_changes,
    previous_month_period,
    previous_quarter_period,
    representative_action_samples,
)


class PriorityInsightServiceTests(unittest.TestCase):
    def test_build_draft_action_events_tracks_include_exclude_order_and_edit(self):
        before = [
            {"id": 1, "title": "기부 기사", "category": "기부/장학/발전기금", "priority": "P2"},
            {"id": 2, "title": "연구 기사", "category": "연구 성과/AI", "priority": "P3"},
            {"id": 3, "title": "행사 기사", "category": "학교 공식 행사", "priority": "P3"},
        ]
        after = [
            {"id": 2, "title": "연구 기사", "category": "연구 성과/AI", "priority": "P1"},
            {"id": 1, "title": "기부 기사", "category": "기부/장학/발전기금", "priority": "P2"},
            {"id": 4, "title": "협약 기사", "category": "협약/사업 선정", "priority": "P2"},
        ]

        events = build_draft_action_events(before, after)
        event_types = [event["action_type"] for event in events]

        self.assertIn("mail_exclude", event_types)
        self.assertIn("mail_include", event_types)
        self.assertIn("order_change", event_types)
        self.assertIn("article_edit", event_types)
        priority_edit = next(
            event for event in events
            if event["action_type"] == "article_edit" and event["article"]["id"] == 2
        )
        self.assertEqual(priority_edit["before"]["priority"], "P3")
        self.assertEqual(priority_edit["after"]["priority"], "P1")

    def test_monthly_fallback_requires_repeated_behavior_and_limits_changes(self):
        actions = [
            {
                "action_type": "mail_exclude",
                "article_category": "인사/위촉",
                "article_title": "인사 기사 1",
                "before": {},
                "after": {},
            },
            {
                "action_type": "mail_exclude",
                "article_category": "인사/위촉",
                "article_title": "인사 기사 2",
                "before": {},
                "after": {},
            },
            {
                "action_type": "mail_include",
                "article_category": "연구 성과/AI",
                "article_title": "연구 기사",
                "before": {},
                "after": {},
            },
        ]

        changes = fallback_priority_changes(actions, cadence="monthly", max_changes=3)

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["target"], "인사/위촉")
        self.assertEqual(changes[0]["change_type"], "lower")
        self.assertEqual(changes[0]["evidence_count"], 2)

    def test_month_and_quarter_periods_use_completed_periods(self):
        month_start, month_end, month_key = previous_month_period(date(2026, 7, 30))
        quarter_start, quarter_end, quarter_key = previous_quarter_period(date(2026, 7, 30))

        self.assertEqual((month_start, month_end, month_key), (date(2026, 6, 1), date(2026, 6, 30), "2026-06"))
        self.assertEqual(
            (quarter_start, quarter_end, quarter_key),
            (date(2026, 4, 1), date(2026, 6, 30), "2026-Q2"),
        )

    def test_representative_samples_respect_workflow_limit_and_keep_groups(self):
        actions = []
        for index in range(40):
            actions.append(
                {
                    "id": index,
                    "action_type": "mail_exclude" if index < 35 else "order_change",
                    "article_category": "인사/위촉" if index < 35 else "연구 성과/AI",
                }
            )

        samples = representative_action_samples(actions, limit=30)

        self.assertEqual(len(samples), 30)
        self.assertTrue(any(item["action_type"] == "order_change" for item in samples))
        self.assertTrue(any(item["article_category"] == "연구 성과/AI" for item in samples))


if __name__ == "__main__":
    unittest.main()
