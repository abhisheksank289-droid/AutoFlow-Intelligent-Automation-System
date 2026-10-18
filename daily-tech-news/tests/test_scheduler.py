import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from pymongo import DESCENDING

from news_service import NewsProviderError
from scheduler import run_daily_news_job, start_scheduler


class RunDailyNewsJobTests(unittest.TestCase):
    @patch("scheduler.print")
    @patch("scheduler.format_briefing", return_value="briefing text")
    @patch("scheduler.save_daily_briefing")
    @patch("scheduler.generate_daily_briefing", return_value={"briefing_date": "2026-10-18"})
    @patch("scheduler.collect_and_store_news", return_value=(3, 1))
    def test_runs_collection_generates_and_saves_briefing(
        self,
        collect_news: MagicMock,
        generate_briefing: MagicMock,
        save_briefing: MagicMock,
        format_text: MagicMock,
        print_text: MagicMock,
    ) -> None:
        database = MagicMock()
        news_collection = MagicMock()
        briefing_collection = MagicMock()
        database.__getitem__.side_effect = {
            "news": news_collection,
            "daily_briefings": briefing_collection,
        }.__getitem__
        articles = [{"title": "Article"}]
        news_collection.find.return_value.sort.return_value = articles
        now = datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc)

        briefing = run_daily_news_job(database, now)

        collect_news.assert_called_once_with(news_collection)
        news_collection.find.assert_called_once_with(
            {"collected_at": {"$gte": now - timedelta(hours=24)}}
        )
        news_collection.find.return_value.sort.assert_called_once_with(
            "published_at",
            DESCENDING,
        )
        generate_briefing.assert_called_once_with(articles, now)
        save_briefing.assert_called_once_with(briefing, briefing_collection)
        format_text.assert_called_once_with(briefing)
        print_text.assert_called_once_with("briefing text")

    @patch(
        "scheduler.collect_and_store_news",
        side_effect=NewsProviderError("service down"),
    )
    def test_does_not_create_success_briefing_after_fetch_failure(
        self,
        collect_news: MagicMock,
    ) -> None:
        database = MagicMock()

        with self.assertRaisesRegex(NewsProviderError, "service down"):
            run_daily_news_job(database)

        database.__getitem__.return_value.find.assert_not_called()


class StartSchedulerTests(unittest.TestCase):
    @patch("scheduler.NEWS_SCHEDULE_HOUR", 7)
    @patch("scheduler.NEWS_SCHEDULE_MINUTE", 15)
    @patch("scheduler.BackgroundScheduler")
    def test_uses_configured_time_and_starts_scheduler(
        self,
        scheduler_class: MagicMock,
    ) -> None:
        database = MagicMock()
        scheduler = scheduler_class.return_value

        result = start_scheduler(database)

        self.assertIs(result, scheduler)
        scheduler.add_job.assert_called_once()
        job_function = scheduler.add_job.call_args.args[0]
        self.assertIs(job_function, run_daily_news_job)
        self.assertEqual(scheduler.add_job.call_args.kwargs["hour"], 7)
        self.assertEqual(scheduler.add_job.call_args.kwargs["minute"], 15)
        self.assertEqual(scheduler.add_job.call_args.kwargs["args"], [database])
        scheduler.start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
