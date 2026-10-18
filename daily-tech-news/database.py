"""Create the MongoDB connection and the collections used by the project."""

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from config import MONGODB_DATABASE, MONGODB_URI

_CONNECTION_ERROR_MESSAGE = (
    "Could not connect to MongoDB. Check that it is running and "
    "that MONGODB_URI is correct."
)


def connect_to_database() -> tuple[MongoClient, Database]:
    """Connect to MongoDB and ensure the required unique indexes exist."""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    except PyMongoError as error:
        raise ConnectionError(_CONNECTION_ERROR_MESSAGE) from error

    try:
        client.admin.command("ping")
        database = client[MONGODB_DATABASE]
        database["news"].create_index("url", unique=True)
        database["news"].create_index("title_key", unique=True)
        database["daily_briefings"].create_index("briefing_date", unique=True)
    except PyMongoError as error:
        client.close()
        raise ConnectionError(_CONNECTION_ERROR_MESSAGE) from error

    return client, database
