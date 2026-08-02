import asyncio
import unittest

from app.api.v1.articles import delete_article
from app.core.errors import AppError


class ArticleDeletePolicyTests(unittest.TestCase):
    def test_direct_article_delete_is_blocked(self):
        with self.assertRaises(AppError) as context:
            asyncio.run(
                delete_article(
                    article_id=123,
                    request=None,
                    db=None,
                    current_user=None,
                )
            )

        self.assertEqual(context.exception.code, "VALIDATION_ERROR")
        self.assertIn("휴지통", context.exception.message)


if __name__ == "__main__":
    unittest.main()
