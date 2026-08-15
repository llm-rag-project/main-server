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

    async def test_section_pool_options_are_normalized_to_gateway_contract(self):
        client = TransNewsClient()
        response = {
            "status": "SUCCESS",
            "message": "ok",
            "data": [],
        }

        with patch.object(client, "_get", new=AsyncMock(return_value=response)) as mocked_get:
            await client.search_news(
                "동국대학교",
                include_section_pools=True,
                section_pool_target_count=20,
                search_sort="date",
            )

        _, kwargs = mocked_get.call_args
        self.assertEqual(kwargs["params"]["section_pool_target_count"], 10)
        self.assertEqual(kwargs["params"]["search_sort"], "latest")
