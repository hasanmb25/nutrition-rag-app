import os
from dotenv import load_dotenv

# Load variables from .env into the environment
load_dotenv()

SUPPORTED_PROVIDERS = ("openai", "gemini", "huggingface")


class Config:
    """Central configuration class to hold and validate environment variables."""

    # Which AI service powers every feature: "openai", "gemini" or "huggingface".
    # Set AI_PROVIDER in .env and restart Streamlit to switch.
    AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").strip().lower()

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    HF_TOKEN = (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACEHUB_API_TOKEN")
        or os.getenv("HUGGINGFACE_API_KEY")
    )

    # >>> SWAP MODELS HERE <<<
    # Change a model by editing its name below, then restart the app.
    # Changing an "embedding" model builds a new recipe vector database on next run.
    MODELS = {
        "openai": {
            "vision": "gpt-4o-mini",      # meal photo analysis
            "recipe": "gpt-4o-mini",      # pantry-to-recipe recommendations
            "critique": "gpt-4o",         # dashboard nutrition report
            "profile": "gpt-4o-mini",     # profile estimate explanation
            "embedding": "text-embedding-3-small",
        },
        "gemini": {
            "vision": "gemini-3.5-flash",
            "recipe": "gemini-3.5-flash",
            "critique": "gemini-3.5-flash",
            "profile": "gemini-3.5-flash",
            "embedding": "gemini-embedding-001",
        },
        "huggingface": {
            "vision": "Qwen/Qwen2.5-VL-7B-Instruct",
            "recipe": "meta-llama/Llama-3.1-8B-Instruct",
            "critique": "meta-llama/Llama-3.1-8B-Instruct",
            "profile": "meta-llama/Llama-3.1-8B-Instruct",
            "embedding": "BAAI/bge-small-en-v1.5",
        },
    }

    # MySQL Settings - defaulting to localhost if not explicitly set
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "nutrition_app")

    @classmethod
    def validate(cls):
        """Fail fast if critical environment variables are missing."""
        if cls.AI_PROVIDER not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"CRITICAL ERROR: AI_PROVIDER must be one of {SUPPORTED_PROVIDERS}, "
                f"got '{cls.AI_PROVIDER}'."
            )
        if cls.AI_PROVIDER == "openai" and not cls.OPENAI_API_KEY:
            raise ValueError("CRITICAL ERROR: OPENAI_API_KEY is missing from the .env file.")
        if cls.AI_PROVIDER == "gemini" and not cls.GOOGLE_API_KEY:
            raise ValueError("CRITICAL ERROR: GOOGLE_API_KEY is missing from the .env file.")
        if cls.AI_PROVIDER == "huggingface" and not cls.HF_TOKEN:
            raise ValueError("CRITICAL ERROR: HF_TOKEN is missing from the .env file.")
        if not cls.MYSQL_USER:
            raise ValueError("CRITICAL ERROR: MYSQL_USER is missing from the .env file.")


# Run validation upon import to ensure the environment is healthy
Config.validate()
