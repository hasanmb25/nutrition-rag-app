import unittest
from unittest.mock import Mock, patch

from account_security import verify_password
import database
from scripts import seed_presentation_demo


class FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.transaction_started = False

    def cursor(self):
        return self.fake_cursor

    def start_transaction(self):
        self.transaction_started = True

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def demo_user(**overrides):
    user = {
        "id": 9,
        "username": seed_presentation_demo.DEMO_USERNAME,
        **seed_presentation_demo.DEMO_PROFILE,
        "openai_profile_consent": True,
    }
    user.update(overrides)
    return user


class PresentationDemoTests(unittest.TestCase):
    def test_existing_demo_account_is_reused_without_prompting_or_editing(self):
        with (
            patch(
                "database.get_user_by_username",
                return_value=demo_user(),
            ),
            patch("database.create_user") as create_user,
        ):
            user_id = seed_presentation_demo.ensure_demo_account(
                input_fn=lambda _prompt: self.fail("unexpected consent prompt"),
                password_fn=lambda _prompt: self.fail("unexpected password prompt"),
            )

        self.assertEqual(user_id, 9)
        create_user.assert_not_called()

    def test_account_creation_requires_openai_consent(self):
        with (
            patch("database.get_user_by_username", return_value=None),
            patch("database.create_user") as create_user,
        ):
            with self.assertRaises(SystemExit):
                seed_presentation_demo.ensure_demo_account(
                    input_fn=lambda _prompt: "no",
                    password_fn=lambda _prompt: self.fail("unexpected password prompt"),
                )

        create_user.assert_not_called()

    def test_new_demo_account_uses_validated_profile_and_hashed_password(self):
        prompts = iter(["yes"])
        passwords = iter(["secure-demo-password", "secure-demo-password"])
        with (
            patch("database.get_user_by_username", return_value=None),
            patch("database.create_user", return_value=12) as create_user,
        ):
            user_id = seed_presentation_demo.ensure_demo_account(
                input_fn=lambda _prompt: next(prompts),
                password_fn=lambda _prompt: next(passwords),
            )

        self.assertEqual(user_id, 12)
        args = create_user.call_args.args
        self.assertEqual(args[0], seed_presentation_demo.DEMO_USERNAME)
        self.assertTrue(verify_password("secure-demo-password", args[1]))
        self.assertEqual(args[2:10], tuple(seed_presentation_demo.DEMO_PROFILE.values()))
        self.assertIs(args[10], True)

    def test_existing_unrelated_account_is_not_modified(self):
        unrelated_user = demo_user(profession="Actual account")
        with (
            patch(
                "database.get_user_by_username",
                return_value=unrelated_user,
            ),
            patch("database.create_user") as create_user,
        ):
            with self.assertRaisesRegex(RuntimeError, "different profile"):
                seed_presentation_demo.ensure_demo_account()

        create_user.assert_not_called()

    def test_meal_seed_replaces_only_demo_rows_for_the_selected_user(self):
        connection = FakeConnection()
        with patch("database.get_connection", return_value=connection):
            seed_presentation_demo.seed_demo_meals(9)

        delete_query, delete_params = connection.fake_cursor.executed[0]
        self.assertIn("DELETE FROM daily_logs", delete_query)
        self.assertIn("user_id = %s AND food_name LIKE %s", delete_query)
        self.assertEqual(
            delete_params,
            (9, f"{seed_presentation_demo.DEMO_MEAL_PREFIX}%"),
        )

        inserts = connection.fake_cursor.executed[1:]
        expected_meals = sum(len(plan) for plan in seed_presentation_demo.MEAL_PLANS)
        self.assertEqual(len(inserts), expected_meals)
        self.assertTrue(all("INSERT INTO daily_logs" in query for query, _ in inserts))
        self.assertTrue(all(params[0] == 9 for _, params in inserts))
        self.assertEqual({params[-2] for _, params in inserts}, set(range(7)))
        self.assertTrue(connection.transaction_started)
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_meal_seed_rolls_back_after_database_error(self):
        connection = FakeConnection()
        connection.fake_cursor.execute = Mock(
            side_effect=database.Error("database error")
        )
        with patch("database.get_connection", return_value=connection):
            with self.assertRaises(database.Error):
                seed_presentation_demo.seed_demo_meals(9)

        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
