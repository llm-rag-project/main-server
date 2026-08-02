import unittest
from unittest.mock import AsyncMock, patch

from app.core.transnews_client import TransNewsClient


class TransNewsClientSearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_lightweight_search_flags_are_forwarded(self):
        client = TransNewsClient()
        response = {
            "status": "SUCCESS",
            "message": "ok",
            "data": [],
        }

        with patch.object(client, "_get", new=AsyncMock(return_value=response)) as mocked_get:
            await client.search_news(
                "동국대학교",
                limit=50,
                timeout_seconds=15,
                discovery_only=True,
                search_sort="relevance",
            )

        _, kwargs = mocked_get.call_args
        self.assertEqual(kwargs["params"]["limit"], 50)
        self.assertEqual(kwargs["params"]["timeout_seconds"], 15)
        self.assertTrue(kwargs["params"]["discovery_only"])
        self.assertEqual(kwargs["params"]["search_sort"], "relevance")

