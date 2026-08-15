import unittest

from app.services.article_identity import canonicalize_article_url, is_same_publisher_article


class CanonicalArticleUrlTests(unittest.TestCase):
    def test_missing_urls_do_not_make_unrelated_articles_identical(self):
        self.assertFalse(
            is_same_publisher_article(
                left_title="동국대 장학기금 전달식 개최",
                left_publisher=None,
                left_content="장학기금 전달 소식",
                left_url=None,
                right_title="동국대 양자소자 특허 기술 개발",
                right_publisher=None,
                right_content="연구팀의 특허 기술 개발 소식",
                right_url=None,
            )
        )

    def test_tracking_parameters_do_not_create_duplicate_urls(self):
        left = canonicalize_article_url(
            "https://www.example.com/news/view?id=123&utm_source=naver"
        )
        right = canonicalize_article_url(
            "http://example.com/news/view?id=123&utm_medium=search"
        )

        self.assertEqual(left, right)

    def test_naver_influx_parameter_does_not_create_duplicate_urls(self):
        left = canonicalize_article_url(
            "https://news.jtbc.co.kr/article/NB12310386?influxDiv=NAVER"
        )
        right = canonicalize_article_url(
            "https://news.jtbc.co.kr/article/NB12310386"
        )

        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
