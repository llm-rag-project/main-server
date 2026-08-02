import unittest
from datetime import date

from app.services.holiday_service import article_collection_window, calculate_collection_start


class CalculateCollectionStartTests(unittest.TestCase):
    def test_monday_includes_weekend(self):
        target = date(2026, 7, 27)
        non_business = {date(2026, 7, 25), date(2026, 7, 26)}

        self.assertEqual(
            calculate_collection_start(target, non_business),
            date(2026, 7, 25),
        )

    def test_next_business_day_includes_full_holiday_chain(self):
        target = date(2026, 8, 17)
        non_business = {
            date(2026, 8, 13),
            date(2026, 8, 14),
            date(2026, 8, 15),
            date(2026, 8, 16),
        }

        self.assertEqual(
            calculate_collection_start(target, non_business),
            date(2026, 8, 13),
        )

    def test_normal_weekday_only_returns_target(self):
        target = date(2026, 7, 28)

        self.assertEqual(calculate_collection_start(target, set()), target)

    def test_holiday_target_does_not_pull_previous_days(self):
        target = date(2026, 8, 15)

        self.assertEqual(calculate_collection_start(target, {target}), target)

    def test_first_day_back_after_personal_vacation_includes_vacation_and_weekend(self):
        target = date(2026, 8, 12)
        non_business = {
            date(2026, 8, 8),
            date(2026, 8, 9),
            date(2026, 8, 10),
            date(2026, 8, 11),
        }

        self.assertEqual(
            calculate_collection_start(target, non_business),
            date(2026, 8, 8),
        )

    def test_article_window_uses_previous_send_boundary_for_normal_day(self):
        start_at, end_at = article_collection_window(
            date(2026, 7, 28),
            date(2026, 7, 28),
            "08:30",
        )

        self.assertEqual(start_at.isoformat(), "2026-07-27T08:30:00+09:00")
        self.assertEqual(end_at.isoformat(), "2026-07-28T08:30:00+09:00")

    def test_article_window_covers_full_weekend_before_monday(self):
        start_at, end_at = article_collection_window(
            date(2026, 7, 25),
            date(2026, 7, 27),
            "08:30",
        )

        self.assertEqual(start_at.isoformat(), "2026-07-24T08:30:00+09:00")
        self.assertEqual(end_at.isoformat(), "2026-07-27T08:30:00+09:00")

    def test_article_window_falls_back_to_default_send_time(self):
        start_at, end_at = article_collection_window(
            date(2026, 7, 28),
            date(2026, 7, 28),
            "invalid",
        )

        self.assertEqual(start_at.hour, 8)
        self.assertEqual(start_at.minute, 30)
        self.assertEqual(end_at.hour, 8)
        self.assertEqual(end_at.minute, 30)


if __name__ == "__main__":
    unittest.main()
