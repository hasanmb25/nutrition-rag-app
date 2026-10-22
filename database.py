import mysql.connector
from mysql.connector import Error
from config import Config

def get_connection(include_db=True):
    """Establish a connection to the MySQL server."""
    try:
        db_config = {
            "host": Config.MYSQL_HOST,
            "user": Config.MYSQL_USER,
            "password": Config.MYSQL_PASSWORD,
        }
        if include_db:
            db_config["database"] = Config.MYSQL_DATABASE
            
        return mysql.connector.connect(**db_config)
    except Error as e:
        print(f"MySQL Connection Error: {e}")
        return None

def init_db():
    """Create the database and required tables if they do not exist."""
    conn = get_connection(include_db=False)
    if not conn:
        return

    try:
        cursor = conn.cursor()
        # Create database
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.MYSQL_DATABASE};")
        
        # Switch to the database
        cursor.execute(f"USE {Config.MYSQL_DATABASE};")
        
        # Create the daily_logs table (No ORM, pure DDL)
        create_table_query = """
        CREATE TABLE IF NOT EXISTS daily_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            food_name VARCHAR(255) NOT NULL,
            weight_g FLOAT NOT NULL,
            calories FLOAT NOT NULL,
            protein FLOAT NOT NULL,
            carbs FLOAT NOT NULL,
            fat FLOAT NOT NULL,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        cursor.execute(create_table_query)
        conn.commit()
        print("Database and 'daily_logs' table initialized successfully.")
    except Error as e:
        print(f"Error initializing database: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn.is_connected():
            conn.close()

def log_meal(food_name: str, weight_g: float, calories: float, protein: float, carbs: float, fat: float):
    """Insert a new meal log into the database using parameterized queries."""
    conn = get_connection()
    if not conn:
        return False
        
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO daily_logs (food_name, weight_g, calories, protein, carbs, fat) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (food_name, weight_g, calories, protein, carbs, fat)
        cursor.execute(query, values)
        conn.commit()
        return True
    except Error as e:
        print(f"Error logging meal: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn.is_connected():
            conn.close()

def get_today_totals():
    """Fetch aggregated macros for the current day using raw SQL SUM()."""
    conn = get_connection()
    if not conn:
        return {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}

    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                COALESCE(SUM(calories), 0) AS total_calories,
                COALESCE(SUM(protein), 0) AS total_protein,
                COALESCE(SUM(carbs), 0) AS total_carbs,
                COALESCE(SUM(fat), 0) AS total_fat
            FROM daily_logs
            WHERE DATE(logged_at) = CURDATE();
        """
        cursor.execute(query)
        result = cursor.fetchone()
        return {
            "calories": round(result["total_calories"], 1),
            "protein": round(result["total_protein"], 1),
            "carbs": round(result["total_carbs"], 1),
            "fat": round(result["total_fat"], 1)
        }
    except Error as e:
        print(f"Error fetching daily totals: {e}")
        return {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    finally:
        if cursor:
            cursor.close()
        if conn.is_connected():
            conn.close()

# Run DB initialization when this file is executed directly
if __name__ == "__main__":
    init_db()