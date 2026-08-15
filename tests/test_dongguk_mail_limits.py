import unittest

from app.api.v1.reports import (
    DonggukMailArticle,
    _is_similar_dongguk_article,
    _dongguk_mail_section_policy,
    _normalize_dongguk_section_limits,
    _sanitize_dongguk_mail_articles,
)


class DonggukMailLimitTest(unittest.TestCase):
    def test_mongolia_heritage_camp_headlines_are_one_topic(self):
        first = DonggukMailArticle(
            id=1,
            title="동국대, 몽골 현지서 2026 한-몽 청년문화유산캠프 진행",
            section="dongguk_core",
            score=55,
        )
        second = DonggukMailArticle(
            id=2,
            title="동국대, 몽골서 청년문화유산캠프 개최, 한몽 대학생 문화교류 확대",
            section="dongguk_core",
            score=66,
        )

        self.assertTrue(_is_similar_dongguk_article(first, second))
        selected, removed = _sanitize_dongguk_mail_articles([first, second])

        self.assertEqual([article.id for article in selected], [2])
        self.assertEqual([article.id for article in removed], [1])
        self.assertIn("같은 주제", removed[0].selection_reason or "")

    def test_default_section_limit_caps_foundation_at_four(self):
        titles = [
            "동국대 총장, 미래 교육 비전 발표",
            "동국대 연구팀, 차세대 배터리 기술 개발",
            "동국대, 지역 상생 업무협약 체결",
            "동국대 학생, 국제 디자인 공모전 대상",
            "동국대 학술원, 한국문학 학술대회 개최",
            "동국대 동문회, 후배 장학금 전달",
        ]
        articles = [
            DonggukMailArticle(
                id=index,
                title=title,
                section="dongguk_core",
                category="학교 공식 행사",
                score=100 - index,
            )
            for index, title in enumerate(titles, start=1)
        ]

        selected, removed = _sanitize_dongguk_mail_articles(articles)

        self.assertEqual(len(selected), 4)
        self.assertEqual(len(removed), 2)
        self.assertTrue(all("최대 기사 수 4건" in (article.selection_reason or "") for article in removed))

    def test_user_section_limits_accept_display_labels(self):
        limits = _normalize_dongguk_section_limits(
            {
                "동국대 [법인/건학위]": 3,
                "대학 [교육]": 1,
                "불교 [종단]": 0,
            }
        )

        self.assertEqual(limits, {"foundation": 3, "education": 1, "buddhism": 0})

    def test_section_policy_result_is_already_sanitized(self):
        first = DonggukMailArticle(
            id=101,
            title="동국대 장학기금 1억원 기부",
            section="dongguk_core",
            category="기부/장학/발전기금",
            score=86,
        )
        duplicate = DonggukMailArticle(
            id=102,
            title="동국대학교에 장학기금 1억 원 전달",
            section="dongguk_core",
            category="기부/장학/발전기금",
            score=80,
        )

        selected, _ = _dongguk_mail_section_policy(
            [first, duplicate],
            [],
            [first, duplicate],
        )
        sanitized, removed = _sanitize_dongguk_mail_articles(selected)

        self.assertEqual(
            [article.id for article in selected],
            [article.id for article in sanitized],
        )
        self.assertEqual(removed, [])


if __name__ == "__main__":
    unittest.main()
