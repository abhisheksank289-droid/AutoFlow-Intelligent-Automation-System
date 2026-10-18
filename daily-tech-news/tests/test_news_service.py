import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import requests
from gnews import RateLimitError
from pymongo.errors import DuplicateKeyError, PyMongoError

from news_service import (
    NewsProviderError,
    fetch_and_normalize_news,
    fetch_news_articles,
    normalize_article,
    save_news_articles,
)


class GNewsTests(unittest.TestCase):
    @patch("news_service.GNews")
    def test_fetches_recent_technology_articles(self, gnews_class: MagicMock) -> None:
        expected_articles = [{"title": "Technology News"}]
        gnews_class.return_value.get_news.return_value = expected_articles

        articles = fetch_news_articles()

        self.assertEqual(articles, expected_articles)
        gnews_class.assert_called_once_with(
            language="en",
            period="1d",
            max_results=10,
        )
        gnews_class.return_value.get_news.assert_called_once()
        query = gnews_class.return_value.get_news.call_args.args[0]
        self.assertIn("quantum computing", query)
        self.assertIn("cybersecurity", query)

    @patch("news_service.GNews")
    def test_empty_results_are_valid(self, gnews_class: MagicMock) -> None:
        gnews_class.return_value.get_news.return_value = []

        self.assertEqual(fetch_news_articles(), [])

    @patch("news_service.GNews")
    def test_reports_network_errors_safely(self, gnews_class: MagicMock) -> None:
        gnews_class.return_value.get_news.side_effect = requests.Timeout(
            "private request details"
        )

        with self.assertRaisesRegex(
            NewsProviderError,
            "Could not fetch news from Google News",
        ) as raised:
            fetch_news_articles()

        self.assertNotIn("private request details", str(raised.exception))

    @patch("news_service.GNews")
    def test_reports_rate_limits(self, gnews_class: MagicMock) -> None:
        gnews_class.return_value.get_news.side_effect = RateLimitError(
            "private provider details"
        )

        with self.assertRaisesRegex(NewsProviderError, "rate-limited") as raised:
            fetch_news_articles()

        self.assertNotIn("private provider details", str(raised.exception))

    @patch("news_service.GNews")
    def test_rejects_invalid_provider_response(self, gnews_class: MagicMock) -> None:
        gnews_class.return_value.get_news.return_value = {"articles": []}

        with self.assertRaisesRegex(
            NewsProviderError,
            "invalid article list",
        ):
            fetch_news_articles()

    @patch("news_service.GNews")
    def test_rejects_non_dictionary_article(self, gnews_class: MagicMock) -> None:
        gnews_class.return_value.get_news.return_value = ["not an article"]

        with self.assertRaisesRegex(NewsProviderError, "invalid article"):
            fetch_news_articles()


class NormalizeArticleTests(unittest.TestCase):
    def test_normalizes_gnews_article(self) -> None:
        article = normalize_article(
            {
                "title": "  Quantum computing breakthrough ",
                "description": "A new qubit design.",
                "publisher": "Example News",
                "url": "https://example.com/news",
                "published date": "Sun, 18 Oct 2026 03:30:00 GMT",
            }
        )

        self.assertIsNotNone(article)
        assert article is not None
        self.assertEqual(
            article["title"], "Quantum computing breakthrough"
        )
        self.assertEqual(
            article["title_key"], "quantum computing breakthrough"
        )
        self.assertEqual(
            article["category"], "Quantum Computing"
        )
        self.assertEqual(article["source"], "Example News")
        self.assertIsNone(article["author"])
        self.assertEqual(
            article["published_at"],
            datetime(2026, 10, 18, 3, 30, tzinfo=timezone.utc),
        )
        self.assertIsNotNone(article["collected_at"].tzinfo)

    def test_parses_google_news_published_date(self) -> None:
        article = normalize_article(
            {
                "title": "Python tools update",
                "url": "https://example.com/python",
                "published date": "Sun, 18 Oct 2026 03:30:00 GMT",
            }
        )

        self.assertIsNotNone(article)
        assert article is not None
        self.assertEqual(
            article["published_at"],
            datetime(2026, 10, 18, 3, 30, tzinfo=timezone.utc),
        )

    def test_skips_article_without_url(self) -> None:
        self.assertIsNone(
            normalize_article({"title": "Article without URL"})
        )

    @patch("news_service.fetch_news_articles")
    def test_fetch_and_normalize_keeps_valid_articles(
        self, fetch: MagicMock
    ) -> None:
        fetch.return_value = [
            {
                "title": "Useful developer tools",
                "url": "https://example.com/tools",
            },
            {"title": "Missing URL"},
        ]

        articles = fetch_and_normalize_news()

        self.assertEqual(len(articles), 1)
        self.assertEqual(
            articles[0]["category"], "Developer Tools"
        )


class SaveNewsArticlesTests(unittest.TestCase):
    def test_inserts_articles_and_returns_counts(self) -> None:
        collection = MagicMock()
        articles = [
            {"url": "https://example.com/one"},
            {"url": "https://example.com/two"},
        ]

        inserted_count, duplicate_count = save_news_articles(
            articles, collection
        )

        self.assertEqual((inserted_count, duplicate_count), (2, 0))
        self.assertEqual(collection.insert_one.call_count, 2)

    def test_counts_duplicate_urls_and_continues(self) -> None:
        collection = MagicMock()
        collection.insert_one.side_effect = [
            DuplicateKeyError("duplicate"),
            MagicMock(),
        ]
        articles = [
            {"url": "https://example.com/one"},
            {"url": "https://example.com/two"},
        ]

        inserted_count, duplicate_count = save_news_articles(
            articles, collection
        )

        self.assertEqual((inserted_count, duplicate_count), (1, 1))

    def test_does_not_hide_other_database_errors(self) -> None:
        collection = MagicMock()
        collection.insert_one.side_effect = PyMongoError(
            "database unavailable"
        )

        with self.assertRaisesRegex(
            PyMongoError, "database unavailable"
        ):
            save_news_articles(
                [{"url": "https://example.com/one"}], collection
            )

    def test_empty_list_inserts_nothing(self) -> None:
        collection = MagicMock()

        self.assertEqual(save_news_articles([], collection), (0, 0))
        collection.insert_one.assert_not_called()


if __name__ == "__main__":
    unittest.main()
