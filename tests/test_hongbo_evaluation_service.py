import unittest

from app.services.hongbo_evaluation_service import build_hongbo_evaluation


class HongboEvaluationServiceTest(unittest.TestCase):
    def test_separates_collection_url_exact_and_topic_rates(self):
        payload = {
            "summary": {"selected_count": 4},
            "dates": {
                "2026-07-08": {
                    "summary": {
                        "홍보처 원본 기사": 4,
                        "정확 일치": 2,
                        "동일 주제·대표 매체 차이": 1,
                    },
                    "details": [
                        {
                            "원본 섹션": "동국대 [법인/건학위]",
                            "비교 결과": "일치",
                            "일치 방식": "URL 일치",
                        },
                        {
                            "원본 섹션": "동국대 [법인/건학위]",
                            "비교 결과": "일치",
                            "일치 방식": "제목 일치",
                        },
                        {
                            "원본 섹션": "대학 [교육]",
                            "비교 결과": "동일 주제 대표 매체 차이",
                            "일치 방식": "동일 주제·다른 대표 기사",
                        },
                        {
                            "원본 섹션": "불교 [종단]",
                            "비교 결과": "일반 수집 누락",
                            "일치 방식": "",
                        },
                    ],
                },
                "2026-07-09": {
                    "summary": {
                        "홍보처 원본 기사": 1,
                        "정확 일치": 0,
                        "동일 주제·대표 매체 차이": 0,
                    },
                    "details": [
                        {
                            "원본 섹션": "불교 [종단]",
                            "비교 결과": "후보 미확보",
                            "일치 방식": "",
                        }
                    ],
                },
            }
        }

        result = build_hongbo_evaluation(payload, target_collection_rate=95, archive_stored_count=5)
        metrics = result["metrics"]

        self.assertEqual(metrics["original_count"], 5)
        self.assertEqual(metrics["automatic_collection_count"], 3)
        self.assertEqual(metrics["recovered_collection_count"], 1)
        self.assertEqual(metrics["candidate_available_count"], 4)
        self.assertEqual(metrics["url_match_count"], 1)
        self.assertEqual(metrics["exact_match_count"], 2)
        self.assertEqual(metrics["topic_inclusive_match_count"], 3)
        self.assertEqual(metrics["automatic_collection_rate"], 60.0)
        self.assertEqual(metrics["candidate_recall_rate"], 80.0)
        self.assertEqual(metrics["url_match_rate"], 20.0)
        self.assertEqual(metrics["exact_match_rate"], 40.0)
        self.assertEqual(metrics["topic_match_rate"], 60.0)
        self.assertEqual(metrics["archive_stored_rate"], 100.0)
        self.assertEqual(result["category_metrics"][0]["archive_stored_count"], 2)
        self.assertEqual(result["category_metrics"][1]["archive_stored_count"], 1)
        self.assertEqual(result["category_metrics"][2]["archive_stored_count"], 2)
        self.assertTrue(all(row["archive_stored_rate"] == 100.0 for row in result["category_metrics"]))
        self.assertEqual(metrics["collection_target_gap_count"], 0)
        self.assertEqual(metrics["policy_comparable_count"], 4)
        self.assertEqual(metrics["policy_adjusted_topic_match_rate"], 75.0)
        self.assertEqual(metrics["candidate_selection_recall_rate"], 75.0)
        self.assertEqual(metrics["end_to_end_match_rate"], 60.0)
        self.assertEqual(metrics["selection_precision_rate"], 75.0)

    def test_keeps_all_three_categories_when_a_category_has_zero_articles(self):
        result = build_hongbo_evaluation({"dates": {}})

        self.assertEqual(
            [item["label"] for item in result["category_metrics"]],
            ["동국대 [법인/건학위]", "대학 [교육]", "불교 [종단]"],
        )
        self.assertTrue(all(item["original_count"] == 0 for item in result["category_metrics"]))


if __name__ == "__main__":
    unittest.main()
