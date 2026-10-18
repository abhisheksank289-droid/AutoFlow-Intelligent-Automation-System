import unittest
from unittest.mock import MagicMock, call, patch

from pymongo.errors import ServerSelectionTimeoutError

from database import connect_to_database


class ConnectToDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = MagicMock()
        self.database = MagicMock()
        self.news_collection = MagicMock()
        self.briefings_collection = MagicMock()
        self.database.__getitem__.side_effect = {
            "news": self.news_collection,
            "daily_briefings": self.briefings_collection,
        }.__getitem__
        self.client.__getitem__.return_value = self.database

    @patch("database.MongoClient")
    def test_connects_and_creates_unique_indexes(self, mongo_client: MagicMock) -> None:
        mongo_client.return_value = self.client

        client, database = connect_to_database()

        self.assertIs(client, self.client)
        self.assertIs(database, self.database)
        self.client.admin.command.assert_called_once_with("ping")
        self.news_collection.create_index.assert_has_calls(
            [
                call("url", unique=True),
                call("title_key", unique=True),
            ]
        )
        self.assertEqual(self.news_collection.create_index.call_count, 2)
        self.briefings_collection.create_index.assert_called_once_with(
            "briefing_date",
            unique=True,
        )

    @patch("database.MongoClient")
    def test_connection_failure_closes_client_and_uses_safe_message(
        self,
        mongo_client: MagicMock,
    ) -> None:
        self.client.admin.command.side_effect = ServerSelectionTimeoutError(
            "private connection details"
        )
        mongo_client.return_value = self.client

        with self.assertRaisesRegex(ConnectionError, "Could not connect to MongoDB"):
            connect_to_database()

        self.client.close.assert_called_once_with()

    @patch("database.MongoClient")
    def test_client_creation_failure_uses_safe_message(
        self,
        mongo_client: MagicMock,
    ) -> None:
        mongo_client.side_effect = ServerSelectionTimeoutError(
            "private connection details"
        )

        with self.assertRaisesRegex(
            ConnectionError,
            "Could not connect to MongoDB",
        ) as raised:
            connect_to_database()

        self.assertNotIn("private connection details", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
