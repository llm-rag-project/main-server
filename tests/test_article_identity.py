import unittest

from app.services.article_identity import canonicalize_article_url


class CanonicalArticleUrlTests(unittest.TestCase):
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
