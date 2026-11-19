"""Single place that builds AI clients for the active provider.

Model names live in config.Config.MODELS; the provider is chosen with
AI_PROVIDER in .env ("openai", "gemini", "huggingface" or "ollama").
"""
import os
import re
import time

import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from config import Config

# Gemini, Hugging Face and Ollama all expose OpenAI-compatible endpoints, so the
# same LangChain client works for every provider; only the URL and key change.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
HF_ROUTER_URL = "https://router.huggingface.co/v1"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

PROVIDER_LABELS = {
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "huggingface": "Hugging Face",
    "ollama": "Ollama (local)",
}
# Ollama ignores the key, but the OpenAI client requires a non-empty one.
OLLAMA_PLACEHOLDER_KEY = "ollama"


def provider_label():
    return PROVIDER_LABELS[Config.AI_PROVIDER]


def provider_status():
    """(active provider label, reason Ollama was skipped or None) for the UI."""
    return provider_label(), Config.FALLBACK_REASON


def ollama_url():
    return f"{Config.OLLAMA_BASE_URL}/v1"


def _endpoint():
    """(base_url, api_key) for the active provider. base_url None = OpenAI default."""
    return {
        "openai": (None, Config.OPENAI_API_KEY),
        "gemini": (GEMINI_URL, Config.GOOGLE_API_KEY),
        "huggingface": (HF_ROUTER_URL, Config.HF_TOKEN),
        "ollama": (ollama_url(), OLLAMA_PLACEHOLDER_KEY),
    }[Config.AI_PROVIDER]


def model_name(task):
    models = Config.MODELS[Config.AI_PROVIDER]
    if task not in models:
        raise ValueError(f"Unknown AI task '{task}'. Expected one of {list(models)}.")
    return models[task]


def get_chat_model(task, temperature=0.0):
    """Chat model for a task ("vision", "recipe", "critique", "profile")."""
    base_url, api_key = _endpoint()
    return ChatOpenAI(
        model=model_name(task),
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_retries=2,
        # seconds; stops a slow model from freezing the app. Local models get
        # longer because the first call also loads the model into GPU memory.
        timeout=180 if Config.AI_PROVIDER == "ollama" else 90,
    )


def get_structured_model(task, schema):
    """Chat model that returns an instance of the given Pydantic schema."""
    llm = get_chat_model(task, temperature=0.0)
    if Config.AI_PROVIDER == "openai":
        return llm.with_structured_output(schema)

    # Other providers' support for OpenAI tool/JSON-schema calling varies, so ask
    # for JSON in the prompt and parse it with Pydantic instead.
    parser = PydanticOutputParser(pydantic_object=schema)
    instructions = SystemMessage(
        content="Respond with only a JSON object and no other text.\n"
        + parser.get_format_instructions()
    )

    def add_format_instructions(prompt):
        messages = prompt.to_messages() if hasattr(prompt, "to_messages") else list(prompt)
        return [instructions, *messages]

    return RunnableLambda(add_format_instructions) | llm | parser


class HuggingFaceInferenceEmbeddings(Embeddings):
    """Embeddings from the Hugging Face Inference API (feature extraction)."""

    def __init__(self, model, token):
        from huggingface_hub import InferenceClient

        self.model = model
        self.client = InferenceClient(provider="hf-inference", api_key=token)

    def _embed(self, text):
        vector = np.asarray(self.client.feature_extraction(text, model=self.model), dtype=float)
        while vector.ndim > 1:  # token-level output: mean-pool to one vector
            vector = vector.mean(axis=0)
        norm = np.linalg.norm(vector)
        return (vector / norm if norm else vector).tolist()

    def embed_documents(self, texts):
        return [self._embed(text) for text in texts]

    def embed_query(self, text):
        return self._embed(text)


class PacedEmbeddings(Embeddings):
    """Embeds documents in batches with a pause between them, to stay under a
    free tier's per-minute limit (Gemini free tier: 100 texts per minute)."""

    def __init__(self, inner, batch_size, pause_seconds):
        self.inner = inner
        self.batch_size = batch_size
        self.pause_seconds = pause_seconds

    def embed_documents(self, texts):
        vectors = []
        for start in range(0, len(texts), self.batch_size):
            if start:
                print(f"Embedded {start}/{len(texts)} texts; waiting "
                      f"{self.pause_seconds}s for the free-tier rate limit...")
                time.sleep(self.pause_seconds)
            vectors.extend(self.inner.embed_documents(texts[start:start + self.batch_size]))
        return vectors

    def embed_query(self, text):
        return self.inner.embed_query(text)


def get_embeddings():
    if Config.AI_PROVIDER == "ollama":
        return OpenAIEmbeddings(
            model=model_name("embedding"),
            api_key=OLLAMA_PLACEHOLDER_KEY,
            base_url=ollama_url(),
            check_embedding_ctx_length=False,  # send text, not OpenAI token IDs
        )
    if Config.AI_PROVIDER == "huggingface":
        return HuggingFaceInferenceEmbeddings(model_name("embedding"), Config.HF_TOKEN)
    if Config.AI_PROVIDER == "gemini":
        gemini = OpenAIEmbeddings(
            model=model_name("embedding"),
            api_key=Config.GOOGLE_API_KEY,
            base_url=GEMINI_URL,
            check_embedding_ctx_length=False,  # send text, not OpenAI token IDs
            chunk_size=90,
            max_retries=6,
        )
        return PacedEmbeddings(gemini, batch_size=90, pause_seconds=65)
    return OpenAIEmbeddings(model=model_name("embedding"), api_key=Config.OPENAI_API_KEY)


def chroma_dir():
    """Vector DB folder. Each embedding model needs its own folder (sizes differ)."""
    embedding_model = model_name("embedding")
    if Config.AI_PROVIDER == "openai" and embedding_model == "text-embedding-3-small":
        return os.path.join(PROJECT_DIR, "chroma_db")  # the original index
    prefix = {"openai": "openai", "gemini": "gemini", "huggingface": "hf", "ollama": "ollama"}[
        Config.AI_PROVIDER
    ]
    slug = re.sub(r"[^A-Za-z0-9]+", "_", embedding_model).strip("_")
    return os.path.join(PROJECT_DIR, f"chroma_db_{prefix}_{slug}")
