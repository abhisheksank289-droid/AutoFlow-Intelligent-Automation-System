import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from briefing_service import (
    format_briefing,
    generate_daily_briefing,
    save_daily_briefing,
    score_article,
    select_top_news,
)


class ScoreArticleTests(unittest.TestCase):
    def test_score_combines_category_recency_and_impact(self) -> None:
        now = datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc)
        article = {
            "category": "AI",
            "title": "Major breakthrough announced",
            "published_at": now - timedelta(hours=2),
        }

        self.assertEqual(score_article(article, now), 10)

    def test_old_or_missing_dates_do_not_receive_recency_points(self) -> None:
        now = datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc)
        old_article = {
            "category": "Cybersecurity",
            "title": "A security update",
            "published_at": now - timedelta(days=10),
        }
        undated_article = {"category": "Cybersecurity", "title": "A security update"}

        self.assertEqual(score_article(old_article, now), 4)
        self.assertEqual(score_article(undated_article, now), 4)


class SelectTopNewsTests(unittest.TestCase):
    def test_selection_is_ranked_limited_and_deduplicated(self) -> None:
        now = datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc)
        articles = [
            {
                "title": "Quantum breakthrough announced",
                "title_key": "quantum breakthrough announced",
                "description": "Researchers report a major result.",
                "url": "https://example.com/quantum",
                "category": "Quantum Computing",
                "published_at": now - timedelta(hours=2),
                "source": "Science News",
            },
            {
                "title": "Quantum breakthrough announced!",
                "title_key": "quantum breakthrough announced",
                "description": "The same report from another source.",
                "url": "https://example.net/quantum",
                "category": "Quantum Computing",
                "published_at": now - timedelta(hours=1),
                "source": "Another News",
            },
            {
                "title": "Cloud launch",
                "description": "A new service launches today.",
                "url": "https://example.com/cloud",
                "category": "Cloud",
                "published_at": now - timedelta(hours=3),
                "source": "Cloud News",
            },
        ]

        selected = select_top_news(articles, now)

        self.assertEqual(len(selected), 2)
        self.assertEqual(selected[0]["category"], "Quantum Computing")
        self.assertEqual(selected[1]["category"], "Cloud")

    def test_limits_articles_per_briefing_section(self) -> None:
        now = datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc)
        articles = [
            {
                "title": f"AI announcement {number}",
                "url": f"https://example.com/ai-{number}",
                "category": "AI",
                "published_at": now - timedelta(minutes=number),
            }
            for number in range(4)
        ]

        selected = select_top_news(articles, now)

        self.assertEqual(len(selected), 2)
        self.assertTrue(all(article["section"] == "AI" for article in selected))


class DailyBriefingTests(unittest.TestCase):
    def test_generates_briefing_for_configured_local_date(self) -> None:
        now = datetime(2026, 10, 18, 0, 30, tzinfo=timezone.utc)
        articles = [
            {
                "title": "A Python developer tools update",
                "description": "A new debugger is available.",
                "url": "https://example.com/debugger",
                "source": "Dev News",
                "category": "Developer Tools",
                "published_at": now,
            }
        ]

        briefing = generate_daily_briefing(articles, now)

        self.assertEqual(briefing["briefing_date"], "2026-10-18")
        self.assertEqual(briefing["total_news"], 1)
        self.assertEqual(briefing["categories"]["Developer Tools"], 1)
        self.assertEqual(len(briefing["top_news"]), 1)
        self.assertIn("debugger", briefing["learning_of_the_day"])
        self.assertIn("CAREER OPPORTUNITY", format_briefing(briefing))

    def test_generates_clear_empty_briefing(self) -> None:
        now = datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc)

        briefing = generate_daily_briefing([], now)
        text = format_briefing(briefing)

        self.assertEqual(briefing["total_news"], 0)
        self.assertEqual(briefing["top_news"], [])
        self.assertIn("No significant articles selected today.", text)
        self.assertIn("LEARNING OF THE DAY", text)

    def test_saves_one_briefing_per_date_using_upsert(self) -> None:
        collection = MagicMock()
        briefing = {
            "briefing_date": "2026-10-18",
            "generated_at": datetime(2026, 10, 18, tzinfo=timezone.utc),
            "created_at": datetime(2026, 10, 18, tzinfo=timezone.utc),
            "total_news": 1,
        }

        save_daily_briefing(briefing, collection)

        collection.update_one.assert_called_once()
        query, update = collection.update_one.call_args.args
        self.assertEqual(query, {"briefing_date": "2026-10-18"})
        self.assertIn("$setOnInsert", update)
        self.assertNotIn("created_at", update["$set"])
        self.assertTrue(collection.update_one.call_args.kwargs["upsert"])


if __name__ == "__main__":
    unittest.main()
