"""Run the news collection and briefing job on a daily schedule."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import DESCENDING
from pymongo.database import Database

from briefing_service import (
    format_briefing,
    generate_daily_briefing,
    save_daily_briefing,
)
from config import NEWS_SCHEDULE_HOUR, NEWS_SCHEDULE_MINUTE, NEWS_TIMEZONE
from news_service import collect_and_store_news

logger = logging.getLogger(__name__)


def run_daily_news_job(
    database: Database,
    now: Optional[datetime] = None,
) -> dict:
    """Fetch news, build a briefing from recent documents, save it, and print it."""
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    current_time = current_time.astimezone(timezone.utc)

    news_collection = database["news"]
    inserted_count, duplicate_count = collect_and_store_news(news_collection)
    logger.info(
        "News collection finished: %s inserted, %s duplicates.",
        inserted_count,
        duplicate_count,
    )

    recent_cutoff = current_time - timedelta(hours=24)
    recent_articles = list(
        news_collection.find({"collected_at": {"$gte": recent_cutoff}}).sort(
            "published_at",
            DESCENDING,
        )
    )

    briefing = generate_daily_briefing(recent_articles, current_time)
    save_daily_briefing(briefing, database["daily_briefings"])
    print(format_briefing(briefing))
    return briefing


def start_scheduler(database: Database) -> BackgroundScheduler:
    """Start the configured daily job and return its scheduler."""
    scheduler = BackgroundScheduler(timezone=ZoneInfo(NEWS_TIMEZONE))
    scheduler.add_job(
        run_daily_news_job,
        trigger="cron",
        hour=NEWS_SCHEDULE_HOUR,
        minute=NEWS_SCHEDULE_MINUTE,
        args=[database],
        id="daily-global-tech-briefing",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
