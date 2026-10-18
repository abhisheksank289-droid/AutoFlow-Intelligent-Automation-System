"""Fetch Google News results and convert them to a consistent format."""

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

import requests
from gnews import GNews, NetworkError, RateLimitError
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from models import categorize_article, normalize_title_key

logger = logging.getLogger(__name__)

NEWS_QUERY = (
    "technology OR artificial intelligence OR agentic AI OR quantum computing "
    "OR cloud computing OR cybersecurity OR programming OR developer tools OR "
    "technology startup"
)
MAX_ARTICLES_PER_REQUEST = 10


class NewsProviderError(Exception):
    """A safe, user-facing error from the news provider."""


def fetch_news_articles() -> list[dict[str, Any]]:
    """Fetch recent English technology articles using the GNews Python package."""
    google_news = GNews(
        language="en",
        period="1d",
        max_results=MAX_ARTICLES_PER_REQUEST,
    )

    try:
        articles = google_news.get_news(NEWS_QUERY)
    except RateLimitError as error:
        raise NewsProviderError(
            "Google News rate-limited the request. Try again later."
        ) from error
    except (NetworkError, requests.RequestException) as error:
        raise NewsProviderError(
            "Could not fetch news from Google News. Check your internet connection."
        ) from error

    if not isinstance(articles, list):
        raise NewsProviderError("Google News returned an invalid article list.")

    if any(not isinstance(article, dict) for article in articles):
        raise NewsProviderError("Google News returned an invalid article.")

    logger.info("Fetched %s articles from Google News.", len(articles))
    return articles


def _parse_published_at(value: Any) -> Optional[datetime]:
    """Convert ISO or RFC-formatted dates to UTC when a date is available."""
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        published_at = value
    elif isinstance(value, str):
        try:
            published_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                published_at = parsedate_to_datetime(value)
            except (TypeError, ValueError, OverflowError):
                logger.warning("Skipping an invalid publication date from Google News.")
                return None
    else:
        logger.warning("Skipping an invalid publication date from Google News.")
        return None

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    return published_at.astimezone(timezone.utc)


def normalize_article(raw_article: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Return a consistent article document, or skip one missing its title or URL."""
    title = raw_article.get("title")
    url = raw_article.get("url")

    if not isinstance(title, str) or not title.strip():
        logger.warning("Skipping a news article without a title.")
        return None

    if not isinstance(url, str) or not url.strip():
        logger.warning("Skipping a news article without a URL.")
        return None

    description = raw_article.get("description")
    if not isinstance(description, str):
        description = ""

    source_data = raw_article.get("source")
    source_name = source_data.get("name") if isinstance(source_data, dict) else None
    if not isinstance(source_name, str):
        publisher = raw_article.get("publisher")
        if isinstance(publisher, dict):
            source_name = publisher.get("title") or publisher.get("name")
        elif isinstance(publisher, str):
            source_name = publisher
        else:
            source_name = ""
    if not isinstance(source_name, str):
        source_name = ""

    author = raw_article.get("author")
    if not isinstance(author, str) or not author.strip():
        author = None

    return {
        "title": title.strip(),
        "title_key": normalize_title_key(title),
        "description": description.strip(),
        "source": source_name.strip(),
        "author": author.strip() if author else None,
        "url": url.strip(),
        "category": categorize_article(title, description),
        "published_at": _parse_published_at(
            raw_article.get("publishedAt", raw_article.get("published date"))
        ),
        "collected_at": datetime.now(timezone.utc),
    }


def fetch_and_normalize_news() -> list[dict[str, Any]]:
    """Fetch provider results and keep only articles with a title and URL."""
    normalized_articles = []

    for raw_article in fetch_news_articles():
        article = normalize_article(raw_article)
        if article is not None:
            normalized_articles.append(article)

    return normalized_articles


def save_news_articles(
    articles: list[dict[str, Any]],
    news_collection: Collection,
) -> tuple[int, int]:
    """Insert new articles and return the inserted and duplicate counts."""
    inserted_count = 0
    duplicate_count = 0

    for article in articles:
        try:
            news_collection.insert_one(article)
            inserted_count += 1
        except DuplicateKeyError:
            duplicate_count += 1

    return inserted_count, duplicate_count


def collect_and_store_news(news_collection: Collection) -> tuple[int, int]:
    """Fetch, normalize, and store news; return inserted and duplicate counts."""
    articles = fetch_and_normalize_news()
    return save_news_articles(articles, news_collection)
