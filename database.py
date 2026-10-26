import json
import re

import mysql.connector
from mysql.connector import Error, IntegrityError

from config import Config


class DuplicateUsernameError(ValueError):
    """Raised when a username is already registered."""


def get_connection(include_db=True):
    """Establish a connection to the configured MySQL server."""
    db_config = {
        "host": Config.MYSQL_HOST,
        "user": Config.MYSQL_USER,
        "password": Config.MYSQL_PASSWORD,
    }
    if include_db:
        db_config["database"] = Config.MYSQL_DATABASE
    return mysql.connector.connect(**db_config)


def _database_name():
    database_name = Config.MYSQL_DATABASE
    if not re.fullmatch(r"[A-Za-z0-9_]+", database_name):
        raise ValueError("MYSQL_DATABASE must contain only letters, digits, or underscores.")
    return database_name


def _column_exists(cursor, table_name, column_name):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (_database_name(), table_name, column_name),
    )
    return cursor.fetchone()[0] > 0


def _index_exists(cursor, table_name, index_name):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_NAME = %s
        """,
        (_database_name(), table_name, index_name),
    )
    return cursor.fetchone()[0] > 0


def _constraint_exists(cursor, table_name, constraint_name):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s
        """,
        (_database_name(), table_name, constraint_name),
    )
    return cursor.fetchone()[0] > 0


def init_db():
    """Create account tables and migrate existing daily logs."""
    database_name = _database_name()
    conn = get_connection(include_db=False)
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database_name}`")
        cursor.execute(f"USE `{database_name}`")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(64) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                age TINYINT UNSIGNED NOT NULL,
                gender_identity VARCHAR(80) NOT NULL,
                sex_for_bmr VARCHAR(16) NULL,
                height_ft TINYINT UNSIGNED NOT NULL,
                height_in TINYINT UNSIGNED NOT NULL,
                weight_kg DECIMAL(6, 2) NOT NULL,
                activity_level VARCHAR(32) NOT NULL,
                profession VARCHAR(120) NOT NULL,
                openai_profile_consent BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
            """
        )
        if not _column_exists(cursor, "users", "openai_profile_consent"):
            cursor.execute(
                "ALTER TABLE users ADD COLUMN openai_profile_consent "
                "BOOLEAN NOT NULL DEFAULT FALSE"
            )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                food_name VARCHAR(255) NOT NULL,
                weight_g FLOAT NOT NULL,
                calories FLOAT NOT NULL,
                protein FLOAT NOT NULL,
                carbs FLOAT NOT NULL,
                fat FLOAT NOT NULL,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
            """
        )
        if not _column_exists(cursor, "daily_logs", "user_id"):
            cursor.execute("ALTER TABLE daily_logs ADD COLUMN user_id INT NULL AFTER id")
        if not _index_exists(cursor, "daily_logs", "idx_daily_logs_user_date"):
            cursor.execute(
                "CREATE INDEX idx_daily_logs_user_date "
                "ON daily_logs (user_id, logged_at)"
            )
        if not _constraint_exists(cursor, "daily_logs", "fk_daily_logs_user"):
            cursor.execute(
                """
                ALTER TABLE daily_logs
                ADD CONSTRAINT fk_daily_logs_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE RESTRICT
                """
            )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_metadata (
                metadata_key VARCHAR(64) PRIMARY KEY,
                metadata_value VARCHAR(64) NOT NULL
            ) ENGINE=InnoDB
            """
        )
        cursor.execute(
            """
            INSERT IGNORE INTO app_metadata (metadata_key, metadata_value)
            VALUES ('account_creation_lock', 'ready')
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS profile_assessments (
                user_id INT PRIMARY KEY,
                assessment_json JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_assessments_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB
            """
        )
        conn.commit()
    except Error:
        conn.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def create_user(
    username,
    password_hash,
    age,
    gender_identity,
    sex_for_bmr,
    height_ft,
    height_in,
    weight_kg,
    activity_level,
    profession,
    openai_profile_consent,
):
    """Create an account and assign unowned historical logs to the first account."""
    if not openai_profile_consent:
        raise ValueError("OpenAI profile-processing consent is required.")
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        conn.start_transaction()
        cursor.execute(
            """
            SELECT metadata_key
            FROM app_metadata
            WHERE metadata_key = 'account_creation_lock'
            FOR UPDATE
            """
        )
        cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM users")
        first_account = cursor.fetchone()[0] == 0
        cursor.execute(
            """
            INSERT INTO users (
                username, password_hash, age, gender_identity, sex_for_bmr,
                height_ft, height_in, weight_kg, activity_level, profession,
                openai_profile_consent
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                username,
                password_hash,
                age,
                gender_identity,
                sex_for_bmr,
                height_ft,
                height_in,
                weight_kg,
                activity_level,
                profession,
                openai_profile_consent,
            ),
        )
        user_id = cursor.lastrowid
        if first_account:
            cursor.execute(
                "UPDATE daily_logs SET user_id = %s WHERE user_id IS NULL",
                (user_id,),
            )
        conn.commit()
        return user_id
    except IntegrityError as error:
        conn.rollback()
        if error.errno == 1062:
            raise DuplicateUsernameError("That username is already registered.") from error
        raise
    except Error:
        conn.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def get_user_by_username(username):
    """Return a user record for authentication, or None when absent."""
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cursor.fetchone()
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def get_user_by_id(user_id):
    """Return profile details for the signed-in user."""
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, username, age, gender_identity, sex_for_bmr,
                   height_ft, height_in, weight_kg, activity_level, profession,
                   openai_profile_consent
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        return cursor.fetchone()
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def log_meal(
    user_id: int,
    food_name: str,
    weight_g: float,
    calories: float,
    protein: float,
    carbs: float,
    fat: float,
):
    """Insert a meal log owned by the signed-in user."""
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO daily_logs
                (user_id, food_name, weight_g, calories, protein, carbs, fat)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(
            query,
            (user_id, food_name, weight_g, calories, protein, carbs, fat),
        )
        conn.commit()
        return True
    except Error:
        conn.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def get_today_totals(user_id):
    """Fetch aggregated macros for this user's current day."""
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(calories), 0) AS total_calories,
                COALESCE(SUM(protein), 0) AS total_protein,
                COALESCE(SUM(carbs), 0) AS total_carbs,
                COALESCE(SUM(fat), 0) AS total_fat
            FROM daily_logs
            WHERE user_id = %s AND DATE(logged_at) = CURDATE()
            """,
            (user_id,),
        )
        result = cursor.fetchone()
        return {
            "calories": round(float(result["total_calories"]), 1),
            "protein": round(float(result["total_protein"]), 1),
            "carbs": round(float(result["total_carbs"]), 1),
            "fat": round(float(result["total_fat"]), 1),
        }
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def get_daily_history(user_id, days=30):
    """Return this user's aggregated daily macros for recent history."""
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                DATE(logged_at) AS log_date,
                COALESCE(SUM(calories), 0) AS calories,
                COALESCE(SUM(protein), 0) AS protein,
                COALESCE(SUM(carbs), 0) AS carbs,
                COALESCE(SUM(fat), 0) AS fat
            FROM daily_logs
            WHERE user_id = %s
              AND logged_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            GROUP BY DATE(logged_at)
            ORDER BY log_date DESC
            """,
            (user_id, days),
        )
        return cursor.fetchall()
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def get_profile_assessment(user_id):
    """Load a previously generated profile assessment."""
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT assessment_json FROM profile_assessments WHERE user_id = %s",
            (user_id,),
        )
        result = cursor.fetchone()
        if result is None:
            return None
        assessment = result[0]
        if isinstance(assessment, str):
            return json.loads(assessment)
        return assessment
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def save_profile_assessment(user_id, assessment):
    """Persist a validated assessment for the owning account."""
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO profile_assessments (user_id, assessment_json)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                assessment_json = VALUES(assessment_json),
                created_at = CURRENT_TIMESTAMP
            """,
            (user_id, json.dumps(assessment)),
        )
        conn.commit()
    except Error:
        conn.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()
