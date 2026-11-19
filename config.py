import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

# Load variables from .env into the environment
load_dotenv()

SUPPORTED_PROVIDERS = ("openai", "gemini", "huggingface", "ollama")


class Config:
    """Central configuration class to hold and validate environment variables."""

    # Which AI service powers every feature: "openai", "gemini", "huggingface"
    # or "ollama" (free local models). Set AI_PROVIDER in .env and restart
    # Streamlit to switch. AI_PROVIDER holds the provider actually in use, which
    # can differ from REQUESTED_PROVIDER when Ollama is unavailable at startup.
    AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").strip().lower()
    REQUESTED_PROVIDER = AI_PROVIDER
    FALLBACK_REASON = None

    # Ollama server. Point this at another PC on your network to use its GPU,
    # e.g. http://192.168.1.20:11434
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/")
    # Used when AI_PROVIDER=ollama but the server or a model is unavailable.
    FALLBACK_PROVIDER = os.getenv("FALLBACK_PROVIDER", "gemini").strip().lower()

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
        # Local models served by Ollama (download each with `ollama pull <name>`).
        # One multimodal model for every chat task avoids swapping models in and
        # out of GPU memory. gemma3:12b needs ~9 GB VRAM; on a smaller GPU try
        # "qwen2.5vl:7b" or "gemma3:4b".
        "ollama": {
            "vision": "gemma3:12b",
            "recipe": "gemma3:12b",
            "critique": "gemma3:12b",
            "profile": "gemma3:12b",
            "embedding": "nomic-embed-text",
        },
    }

    # MySQL Settings - defaulting to localhost if not explicitly set
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "nutrition_app")

    @classmethod
    def ollama_problem(cls, timeout=2.0):
        """Return why Ollama can't serve the configured models, or None if it can."""
        url = f"{cls.OLLAMA_BASE_URL}/api/tags"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                payload = json.load(response)
        except (urllib.error.URLError, OSError, ValueError):
            return f"Ollama is not reachable at {cls.OLLAMA_BASE_URL}"
        installed = set()
        for model in payload.get("models", []):
            name = model.get("name", "")
            installed.add(name)
            if name.endswith(":latest"):
                installed.add(name[: -len(":latest")])
        missing = sorted(
            name for name in set(cls.MODELS["ollama"].values()) if name not in installed
        )
        if missing:
            return f"Ollama model(s) not downloaded: {', '.join(missing)}"
        return None

    @classmethod
    def resolve_provider(cls):
        """Switch from Ollama to FALLBACK_PROVIDER if Ollama can't be used."""
        cls.REQUESTED_PROVIDER = cls.AI_PROVIDER
        cls.FALLBACK_REASON = None
        if cls.AI_PROVIDER != "ollama":
            return
        problem = cls.ollama_problem()
        if problem is None:
            return
        if cls.FALLBACK_PROVIDER in ("", "none", "ollama"):
            raise ValueError(f"CRITICAL ERROR: {problem}, and no FALLBACK_PROVIDER is set.")
        print(f"WARNING: {problem}. Falling back to AI_PROVIDER={cls.FALLBACK_PROVIDER}.")
        cls.FALLBACK_REASON = problem
        cls.AI_PROVIDER = cls.FALLBACK_PROVIDER

    @classmethod
    def validate(cls):
        """Fail fast if critical environment variables are missing."""
        if cls.FALLBACK_REASON and cls.AI_PROVIDER not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"CRITICAL ERROR: {cls.FALLBACK_REASON}, and FALLBACK_PROVIDER "
                f"'{cls.AI_PROVIDER}' is not one of {SUPPORTED_PROVIDERS}."
            )
        if cls.AI_PROVIDER not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"CRITICAL ERROR: AI_PROVIDER must be one of {SUPPORTED_PROVIDERS}, "
                f"got '{cls.AI_PROVIDER}'."
            )
        if cls.AI_PROVIDER == "openai" and not cls.OPENAI_API_KEY:
            raise ValueError("CRITICAL ERROR: OPENAI_API_KEY is missing from the .env file.")
        if cls.AI_PROVIDER == "gemini" and not cls.GOOGLE_API_KEY:
            if cls.FALLBACK_REASON:
                raise ValueError(
                    f"CRITICAL ERROR: {cls.FALLBACK_REASON}, and the Gemini fallback "
                    "needs GOOGLE_API_KEY in the .env file."
                )
            raise ValueError("CRITICAL ERROR: GOOGLE_API_KEY is missing from the .env file.")
        if cls.AI_PROVIDER == "huggingface" and not cls.HF_TOKEN:
            raise ValueError("CRITICAL ERROR: HF_TOKEN is missing from the .env file.")
        if not cls.MYSQL_USER:
            raise ValueError("CRITICAL ERROR: MYSQL_USER is missing from the .env file.")


# Pick the provider (Ollama falls back if unavailable), then make sure the
# environment is healthy. Runs once when the app starts.
Config.resolve_provider()
Config.validate()
