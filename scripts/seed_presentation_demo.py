from getpass import getpass

from mysql.connector import Error as MySQLError

import database
from account_security import hash_password, validate_profile


DEMO_USERNAME = "nutrifyuser"
DEMO_MEAL_PREFIX = "[Presentation demo] "

DEMO_PROFILE = {
    "age": 29,
    "gender_identity": "Woman",
    "sex_for_bmr": "female",
    "height_ft": 5,
    "height_in": 6,
    "weight_kg": 68.2,
    "activity_level": "Moderately active",
    "profession": "Presentation demo profile",
}

MEAL_PLANS = (
    (
        ("Oatmeal with berries", 350, 420, 18, 63, 10),
        ("Chicken quinoa bowl", 430, 620, 43, 68, 17),
        ("Salmon with sweet potato", 420, 610, 39, 55, 24),
    ),
    (
        ("Greek yogurt and granola", 320, 390, 24, 49, 9),
        ("Lentil soup and whole-grain toast", 480, 540, 27, 79, 12),
        ("Tofu vegetable stir-fry", 440, 590, 30, 66, 23),
    ),
    (
        ("Scrambled eggs and avocado toast", 310, 460, 24, 38, 22),
        ("Turkey and brown rice bowl", 420, 570, 41, 63, 13),
        ("Shrimp pasta with vegetables", 430, 640, 38, 78, 17),
    ),
    (
        ("Banana peanut butter oatmeal", 340, 450, 16, 65, 14),
        ("Chickpea salad with pita", 400, 560, 22, 82, 15),
        ("Chicken fajita bowl", 450, 650, 46, 70, 18),
    ),
    (
        ("Cottage cheese fruit bowl", 300, 360, 28, 42, 7),
        ("Tuna avocado sandwich", 370, 520, 34, 54, 18),
        ("Beef and vegetable stew", 460, 620, 39, 58, 22),
    ),
    (
        ("Spinach feta omelet", 300, 410, 29, 12, 27),
        ("Baked falafel grain bowl", 430, 610, 24, 82, 19),
        ("Baked cod with potatoes", 440, 570, 38, 62, 15),
    ),
    (
        ("Overnight oats with apple", 350, 400, 17, 66, 9),
        ("Grilled chicken wrap", 390, 590, 42, 61, 18),
        ("Vegetable curry with rice", 460, 640, 19, 96, 19),
    ),
)


def _matches_demo_profile(user):
    try:
        return (
            user["username"] == DEMO_USERNAME
            and int(user["age"]) == DEMO_PROFILE["age"]
            and user["gender_identity"] == DEMO_PROFILE["gender_identity"]
            and user["sex_for_bmr"] == DEMO_PROFILE["sex_for_bmr"]
            and int(user["height_ft"]) == DEMO_PROFILE["height_ft"]
            and int(user["height_in"]) == DEMO_PROFILE["height_in"]
            and float(user["weight_kg"]) == DEMO_PROFILE["weight_kg"]
            and user["activity_level"] == DEMO_PROFILE["activity_level"]
            and user["profession"] == DEMO_PROFILE["profession"]
        )
    except (KeyError, TypeError, ValueError):
        return False


def ensure_demo_account(input_fn=None, password_fn=None):
    user = database.get_user_by_username(DEMO_USERNAME)
    if user is not None:
        if not _matches_demo_profile(user):
            raise RuntimeError(
                f"The reserved username '{DEMO_USERNAME}' already belongs to a "
                "different profile. No account data was changed."
            )
        if not user["openai_profile_consent"]:
            raise RuntimeError(
                "The demo account has not consented to OpenAI processing. "
                "Review or recreate it through the account registration form."
            )
        return int(user["id"])

    prompt = input if input_fn is None else input_fn
    read_password = getpass if password_fn is None else password_fn
    consent = prompt(
        "This fictional profile's age, height, weight, activity level, and BMR sex "
        "may be sent to OpenAI for estimates. Continue? [y/N] "
    )
    if consent.strip().lower() not in {"y", "yes"}:
        raise SystemExit("Demo account was not created; OpenAI consent was not given.")

    password = read_password(
        f"Choose a password for {DEMO_USERNAME} (10-128 characters): "
    )
    confirmation = read_password("Confirm the demo account password: ")
    if password != confirmation:
        raise ValueError("The password and confirmation do not match.")

    username = validate_profile(
        DEMO_USERNAME,
        password,
        DEMO_PROFILE["age"],
        DEMO_PROFILE["gender_identity"],
        DEMO_PROFILE["height_ft"],
        DEMO_PROFILE["height_in"],
        DEMO_PROFILE["weight_kg"],
        DEMO_PROFILE["activity_level"],
        DEMO_PROFILE["profession"],
    )
    return database.create_user(
        username,
        hash_password(password),
        DEMO_PROFILE["age"],
        DEMO_PROFILE["gender_identity"],
        DEMO_PROFILE["sex_for_bmr"],
        DEMO_PROFILE["height_ft"],
        DEMO_PROFILE["height_in"],
        DEMO_PROFILE["weight_kg"],
        DEMO_PROFILE["activity_level"],
        DEMO_PROFILE["profession"],
        True,
    )


def seed_demo_meals(user_id):
    connection = database.get_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        connection.start_transaction()
        cursor.execute(
            """
            DELETE FROM daily_logs
            WHERE user_id = %s AND food_name LIKE %s
            """,
            (user_id, f"{DEMO_MEAL_PREFIX}%"),
        )
        for days_ago, meal_plan in enumerate(reversed(MEAL_PLANS)):
            for hour, meal in zip((8, 12, 18), meal_plan):
                food_name, weight_g, calories, protein, carbs, fat = meal
                cursor.execute(
                    """
                    INSERT INTO daily_logs
                        (user_id, food_name, weight_g, calories, protein, carbs, fat, logged_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s,
                            DATE_SUB(CURDATE(), INTERVAL %s DAY) + INTERVAL %s HOUR)
                    """,
                    (
                        user_id,
                        f"{DEMO_MEAL_PREFIX}{food_name}",
                        weight_g,
                        calories,
                        protein,
                        carbs,
                        fat,
                        days_ago,
                        hour,
                    ),
                )
        connection.commit()
    except MySQLError:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def main():
    database.init_db()
    user_id = ensure_demo_account()
    seed_demo_meals(user_id)
    print(
        f"Presentation data is ready for user ID {user_id} "
        f"({DEMO_USERNAME}). Sign in with the password you set."
    )


if __name__ == "__main__":
    main()
