import unittest
from unittest.mock import patch

import database


class FakeCursor:
    def __init__(self, user_count=0, totals=None):
        self.user_count = user_count
        self.totals = totals or {
            "total_calories": 420.5,
            "total_protein": 20,
            "total_carbs": 30,
            "total_fat": 10,
        }
        self.executed = []
        self.last_query = ""
        self.lastrowid = 42

    def execute(self, query, params=None):
        self.last_query = query
        self.executed.append((query, params))

    def fetchone(self):
        if "SELECT COUNT(*) FROM users" in self.last_query:
            return (self.user_count,)
        if "account_creation_lock" in self.last_query:
            return ("account_creation_lock",)
        if "SUM(calories)" in self.last_query:
            return self.totals
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self, **kwargs):
        return self.fake_cursor

    def start_transaction(self):
        pass

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class DatabaseAccountScopeTests(unittest.TestCase):
    def test_daily_totals_query_is_scoped_to_user_and_today(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)

        with patch("database.get_connection", return_value=connection):
            totals = database.get_today_totals(17)

        query, params = cursor.executed[0]
        self.assertIn("user_id = %s", query)
        self.assertIn("DATE(logged_at) = CURDATE()", query)
        self.assertEqual(params, (17,))
        self.assertEqual(totals["calories"], 420.5)

    def test_meal_insert_includes_user_id(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)

        with patch("database.get_connection", return_value=connection):
            database.log_meal(17, "Soup", 300, 250, 10, 30, 8)

        query, params = cursor.executed[0]
        self.assertIn("(user_id, food_name", query)
        self.assertEqual(params[0], 17)
        self.assertTrue(connection.committed)

    def test_first_account_claims_existing_unowned_logs(self):
        cursor = FakeCursor(user_count=0)
        connection = FakeConnection(cursor)

        with patch("database.get_connection", return_value=connection):
            user_id = database.create_user(
                "first_user",
                "scrypt-hash",
                30,
                "Woman",
                "female",
                5,
                5,
                60,
                "Moderately active",
                "Student",
                True,
            )

        updates = [
            params
            for query, params in cursor.executed
            if "UPDATE daily_logs SET user_id" in query
        ]
        self.assertEqual(user_id, 42)
        self.assertEqual(updates, [(42,)])
        self.assertTrue(connection.committed)


if __name__ == "__main__":
    unittest.main()
