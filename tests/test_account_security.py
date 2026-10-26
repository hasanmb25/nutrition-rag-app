import unittest

from account_security import hash_password, validate_profile, verify_password


class AccountSecurityTests(unittest.TestCase):
    def test_password_hash_verifies_only_the_original_password(self):
        encoded_hash = hash_password("correct-horse-battery")

        self.assertTrue(verify_password("correct-horse-battery", encoded_hash))
        self.assertFalse(verify_password("different-password", encoded_hash))

    def test_profile_requires_adult_age(self):
        with self.assertRaisesRegex(ValueError, "18\\+"):
            validate_profile(
                "nutrify_user",
                "long-enough-password",
                17,
                "Prefer not to say",
                5,
                8,
                70,
                "Moderately active",
                "Student",
            )

    def test_profile_rejects_short_password(self):
        with self.assertRaisesRegex(ValueError, "10 and 128"):
            validate_profile(
                "nutrify_user",
                "short",
                25,
                "Woman",
                5,
                8,
                70,
                "Moderately active",
                "Student",
            )

    def test_profile_returns_trimmed_username(self):
        username = validate_profile(
            " nutrify_user ",
            "long-enough-password",
            25,
            "Woman",
            5,
            8,
            70,
            "Moderately active",
            "Student",
        )

        self.assertEqual(username, "nutrify_user")


if __name__ == "__main__":
    unittest.main()
