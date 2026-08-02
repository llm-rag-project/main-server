import unittest

from app.api.v1.articles import _clean_search_summary


class CleanSearchSummaryTests(unittest.TestCase):
    def test_rejects_heavily_garbled_text(self):
        self.assertIsNone(_clean_search_summary("���� ���� ����"))

    def test_preserves_normal_korean_summary(self):
        summary = "동국대학교가 산학협력 업무협약을 체결했습니다."

        self.assertEqual(_clean_search_summary(summary), summary)


if __name__ == "__main__":
    unittest.main()
