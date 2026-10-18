"""Start the Daily Global Tech News Scheduler."""

import argparse
import logging
import re
from datetime import date, datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from flask import Flask, jsonify, request
from pymongo import DESCENDING
from pymongo.database import Database
from pymongo.errors import PyMongoError

from database import connect_to_database
from models import CATEGORIES
from news_service import NewsProviderError
from scheduler import run_daily_news_job, start_scheduler

logger = logging.getLogger(__name__)

NEWS_PAGE_SIZE = 50
BRIEFING_PAGE_SIZE = 30


def _to_json_safe(value: Any) -> Any:
    """Convert MongoDB values to types supported by Flask's JSON response."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _to_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_json_safe(item) for item in value]
    return value


def create_app(database: Database) -> Flask:
    """Create the Flask app with routes backed by the supplied database."""
    app = Flask(__name__)

    @app.errorhandler(PyMongoError)
    def handle_database_error(error: PyMongoError):
        logger.error("Database request failed (%s).", type(error).__name__)
        return jsonify({"error": "Database operation failed."}), 503

    @app.get("/health")
    def health():
        try:
            database.command("ping")
        except PyMongoError as error:
            logger.error("Health check failed (%s).", type(error).__name__)
            return (
                jsonify({"status": "unavailable", "error": "Database is unavailable."}),
                503,
            )

        return jsonify({"status": "ok", "database": "connected"}), 200

    @app.get("/news")
    def get_news():
        articles = list(
            database["news"]
            .find()
            .sort("collected_at", DESCENDING)
            .limit(NEWS_PAGE_SIZE)
        )
        return jsonify(
            {
                "count": len(articles),
                "news": _to_json_safe(articles),
            }
        ), 200

    @app.get("/news/search")
    def search_news():
        keyword = request.args.get("keyword", "").strip()
        if not keyword:
            return jsonify({"error": "The keyword query parameter is required."}), 400
        if len(keyword) > 100:
            return (
                jsonify({"error": "The keyword must be 100 characters or fewer."}),
                400,
            )

        safe_pattern = re.escape(keyword)
        query = {
            "$or": [
                {"title": {"$regex": safe_pattern, "$options": "i"}},
                {"description": {"$regex": safe_pattern, "$options": "i"}},
                {"category": {"$regex": safe_pattern, "$options": "i"}},
            ]
        }
        articles = list(
            database["news"]
            .find(query)
            .sort("collected_at", DESCENDING)
            .limit(NEWS_PAGE_SIZE)
        )
        return jsonify(
            {
                "count": len(articles),
                "news": _to_json_safe(articles),
            }
        ), 200

    @app.get("/news/category/<category>")
    def get_news_by_category(category: str):
        matching_category = next(
            (item for item in CATEGORIES if item.casefold() == category.casefold()),
            None,
        )
        if matching_category is None:
            return jsonify({"error": "Invalid news category."}), 400

        articles = list(
            database["news"]
            .find({"category": matching_category})
            .sort("collected_at", DESCENDING)
            .limit(NEWS_PAGE_SIZE)
        )
        return jsonify(
            {
                "count": len(articles),
                "news": _to_json_safe(articles),
            }
        ), 200

    @app.get("/news/<article_id>")
    def get_article(article_id: str):
        try:
            object_id = ObjectId(article_id)
        except InvalidId:
            return (
                jsonify({"error": "Article ID must be a valid MongoDB ObjectId."}),
                400,
            )

        article = database["news"].find_one({"_id": object_id})
        if article is None:
            return jsonify({"error": "Article not found."}), 404

        return jsonify(_to_json_safe(article)), 200

    @app.get("/briefings")
    def get_briefings():
        briefings = list(
            database["daily_briefings"]
            .find()
            .sort("briefing_date", DESCENDING)
            .limit(BRIEFING_PAGE_SIZE)
        )
        return jsonify(
            {
                "count": len(briefings),
                "briefings": _to_json_safe(briefings),
            }
        ), 200

    @app.get("/briefings/<briefing_date>")
    def get_briefing(briefing_date: str):
        try:
            parsed_date = date.fromisoformat(briefing_date)
        except ValueError:
            return jsonify({"error": "Date must use the YYYY-MM-DD format."}), 400
        if parsed_date.isoformat() != briefing_date:
            return jsonify({"error": "Date must use the YYYY-MM-DD format."}), 400

        briefing = database["daily_briefings"].find_one(
            {"briefing_date": briefing_date}
        )
        if briefing is None:
            return jsonify({"error": "Briefing not found."}), 404

        return jsonify(_to_json_safe(briefing)), 200

    return app


def main(arguments: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Daily Global Tech News Scheduler")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run the news and briefing job once, then exit.",
    )
    args = parser.parse_args(arguments)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        client, database = connect_to_database()
    except ConnectionError as error:
        logger.error("%s", error)
        return 1

    scheduler = None
    try:
        if args.run_now:
            run_daily_news_job(database)
            return 0

        app = create_app(database)
        scheduler = start_scheduler(database)
        logger.info("Starting API and scheduler. Press Ctrl+C to stop.")
        app.run(host="127.0.0.1", port=5000)
    except KeyboardInterrupt:
        logger.info("Stopping the application.")
    except NewsProviderError as error:
        logger.error("%s", error)
        return 1
    finally:
        if scheduler is not None and scheduler.running:
            scheduler.shutdown(wait=True)
        client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
