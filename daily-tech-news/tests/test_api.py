import unittest
from datetime import datetime
from unittest.mock import MagicMock

from bson import ObjectId
from pymongo.errors import ServerSelectionTimeoutError

from main import create_app


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents
        self.sort_call = None
        self.limit_value = None

    def sort(self, field, direction):
        self.sort_call = (field, direction)
        return self

    def limit(self, count):
        self.limit_value = count
        return self

    def __iter__(self):
        return iter(self.documents)


class ApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MagicMock()
        self.news_collection = MagicMock()
        self.briefings_collection = MagicMock()
        self.database.__getitem__.side_effect = {
            "news": self.news_collection,
            "daily_briefings": self.briefings_collection,
        }.__getitem__
        self.app = create_app(self.database)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def set_news_results(self, documents) -> None:
        self.news_collection.find.return_value = FakeCursor(documents)

    def set_briefing_results(self, documents) -> None:
        self.briefings_collection.find.return_value = FakeCursor(documents)

    def test_health_returns_database_status(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok", "database": "connected"})
        self.database.command.assert_called_once_with("ping")

    def test_health_returns_safe_unavailable_response(self) -> None:
        self.database.command.side_effect = ServerSelectionTimeoutError(
            "private connection details"
        )

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json,
            {"status": "unavailable", "error": "Database is unavailable."},
        )
        self.assertNotIn("private connection details", response.get_data(as_text=True))

    def test_latest_news_serializes_object_id_and_datetime(self) -> None:
        article_id = ObjectId()
        collected_at = datetime(2026, 10, 18)
        self.set_news_results(
            [{"_id": article_id, "title": "Python update", "collected_at": collected_at}]
        )

        response = self.client.get("/news")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["count"], 1)
        self.assertEqual(response.json["news"][0]["_id"], str(article_id))
        self.assertEqual(
            response.json["news"][0]["collected_at"],
            "2026-10-18T00:00:00+00:00",
        )
        self.assertEqual(
            self.news_collection.find.return_value.sort_call,
            ("collected_at", -1),
        )
        self.assertEqual(self.news_collection.find.return_value.limit_value, 50)

    def test_article_route_returns_one_document(self) -> None:
        article_id = ObjectId()
        self.news_collection.find_one.return_value = {"_id": article_id, "title": "News"}

        response = self.client.get(f"/news/{article_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["_id"], str(article_id))

    def test_invalid_article_id_returns_bad_request(self) -> None:
        response = self.client.get("/news/not-an-object-id")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json["error"],
            "Article ID must be a valid MongoDB ObjectId.",
        )

    def test_missing_article_returns_not_found(self) -> None:
        self.news_collection.find_one.return_value = None

        response = self.client.get(f"/news/{ObjectId()}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json["error"], "Article not found.")

    def test_category_filter_validates_category(self) -> None:
        self.set_news_results([{"title": "Quantum research"}])

        response = self.client.get("/news/category/Quantum%20Computing")

        self.assertEqual(response.status_code, 200)
        self.news_collection.find.assert_called_once_with(
            {"category": "Quantum Computing"}
        )

    def test_invalid_category_returns_bad_request(self) -> None:
        response = self.client.get("/news/category/Unknown")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"], "Invalid news category.")
        self.news_collection.find.assert_not_called()

    def test_search_requires_keyword(self) -> None:
        response = self.client.get("/news/search")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json["error"],
            "The keyword query parameter is required.",
        )

    def test_search_escapes_regex_and_checks_all_fields(self) -> None:
        self.set_news_results([{"title": "Python news"}])

        response = self.client.get("/news/search?keyword=%5B")

        self.assertEqual(response.status_code, 200)
        self.news_collection.find.assert_called_once_with(
            {
                "$or": [
                    {"title": {"$regex": r"\[", "$options": "i"}},
                    {"description": {"$regex": r"\[", "$options": "i"}},
                    {"category": {"$regex": r"\[", "$options": "i"}},
                ]
            }
        )

    def test_briefing_list_and_detail(self) -> None:
        briefing = {"briefing_date": "2026-10-18", "total_news": 3}
        self.set_briefing_results([briefing])
        self.briefings_collection.find_one.return_value = briefing

        list_response = self.client.get("/briefings")
        detail_response = self.client.get("/briefings/2026-10-18")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json["briefings"], [briefing])
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json, briefing)

    def test_invalid_briefing_date_returns_bad_request(self) -> None:
        response = self.client.get("/briefings/2026-02-30")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json["error"],
            "Date must use the YYYY-MM-DD format.",
        )

    def test_missing_briefing_returns_not_found(self) -> None:
        self.briefings_collection.find_one.return_value = None

        response = self.client.get("/briefings/2026-10-18")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json["error"], "Briefing not found.")

    def test_database_errors_return_safe_service_unavailable(self) -> None:
        self.news_collection.find.side_effect = ServerSelectionTimeoutError(
            "private connection details"
        )

        response = self.client.get("/news")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {"error": "Database operation failed."})
        self.assertNotIn("private connection details", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
