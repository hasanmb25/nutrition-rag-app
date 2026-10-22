import os
from dotenv import load_dotenv

# Load variables from .env into the environment
load_dotenv()

class Config:
    """Central configuration class to hold and validate environment variables."""
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # MySQL Settings - defaulting to localhost if not explicitly set
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "nutrition_app")

    @classmethod
    def validate(cls):
        """Fail fast if critical environment variables are missing."""
        if not cls.OPENAI_API_KEY:
            raise ValueError("CRITICAL ERROR: OPENAI_API_KEY is missing from the .env file.")
        if not cls.MYSQL_USER:
            raise ValueError("CRITICAL ERROR: MYSQL_USER is missing from the .env file.")

# Run validation upon import to ensure the environment is healthy
Config.validate()