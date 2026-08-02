import unittest

from app.core.metrics import normalize_route


class NormalizeRouteTests(unittest.TestCase):
    def test_replaces_numeric_path_segments(self):
        self.assertEqual(normalize_route("/api/v1/articles/123"), "/api/v1/articles/{id}")

    def test_replaces_uuid_path_segments(self):
        self.assertEqual(
            normalize_route("/api/v1/runs/550e8400-e29b-41d4-a716-446655440000/status"),
            "/api/v1/runs/{id}/status",
        )

    def test_keeps_static_routes(self):
        self.assertEqual(normalize_route("/api/v1/reports/dongguk"), "/api/v1/reports/dongguk")

    def test_empty_path_becomes_root(self):
        self.assertEqual(normalize_route(""), "/")


if __name__ == "__main__":
    unittest.main()
