import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel

import ai_models
from config import Config


class Answer(BaseModel):
    value: str


def use_provider(provider):
    return patch.multiple(
        Config,
        AI_PROVIDER=provider,
        OPENAI_API_KEY="test-openai-key",
        GOOGLE_API_KEY="test-google-key",
        HF_TOKEN="test-hf-token",
        OLLAMA_BASE_URL="http://ollama-host:11434",
        FALLBACK_REASON=None,
    )


class ModelSelectionTests(unittest.TestCase):
    def test_every_task_uses_the_name_from_config(self):
        for provider in ("openai", "gemini", "huggingface", "ollama"):
            with use_provider(provider):
                for task in ("vision", "recipe", "critique", "profile"):
                    model = ai_models.get_chat_model(task)
                    self.assertEqual(model.model_name, Config.MODELS[provider][task])

    def test_openai_uses_default_endpoint(self):
        with use_provider("openai"):
            self.assertIsNone(ai_models.get_chat_model("recipe").openai_api_base)
            self.assertEqual(ai_models.provider_label(), "OpenAI")

    def test_huggingface_uses_router_endpoint(self):
        with use_provider("huggingface"):
            model = ai_models.get_chat_model("recipe")
            self.assertEqual(model.openai_api_base, ai_models.HF_ROUTER_URL)
            self.assertEqual(model.openai_api_key.get_secret_value(), "test-hf-token")
            self.assertEqual(ai_models.provider_label(), "Hugging Face")

    def test_gemini_uses_openai_compatible_endpoint(self):
        with use_provider("gemini"):
            model = ai_models.get_chat_model("vision")
            self.assertEqual(model.openai_api_base, ai_models.GEMINI_URL)
            self.assertEqual(model.openai_api_key.get_secret_value(), "test-google-key")
            embeddings = ai_models.get_embeddings()
            self.assertIsInstance(embeddings, ai_models.PacedEmbeddings)
            self.assertLessEqual(embeddings.batch_size, 100)  # free tier: 100/minute
            self.assertEqual(embeddings.inner.openai_api_base, ai_models.GEMINI_URL)
            self.assertFalse(embeddings.inner.check_embedding_ctx_length)

    def test_ollama_uses_local_openai_compatible_endpoint(self):
        with use_provider("ollama"):
            model = ai_models.get_chat_model("vision")
            self.assertEqual(model.openai_api_base, "http://ollama-host:11434/v1")
            self.assertEqual(model.request_timeout, 180)
            self.assertEqual(ai_models.provider_label(), "Ollama (local)")
            embeddings = ai_models.get_embeddings()
            self.assertNotIsInstance(embeddings, ai_models.PacedEmbeddings)
            self.assertEqual(embeddings.openai_api_base, "http://ollama-host:11434/v1")
            self.assertEqual(embeddings.model, Config.MODELS["ollama"]["embedding"])
            self.assertFalse(embeddings.check_embedding_ctx_length)

    def test_paced_embeddings_batches_and_pauses(self):
        calls = []

        class FakeEmbeddings:
            def embed_documents(self, texts):
                calls.append(len(texts))
                return [[0.0] for _ in texts]

        paced = ai_models.PacedEmbeddings(FakeEmbeddings(), batch_size=90, pause_seconds=65)
        with patch.object(ai_models.time, "sleep") as sleep:
            vectors = paced.embed_documents(["x"] * 200)

        self.assertEqual(calls, [90, 90, 20])
        self.assertEqual(len(vectors), 200)
        self.assertEqual(sleep.call_count, 2)

    def test_unknown_task_is_rejected(self):
        with use_provider("openai"):
            with self.assertRaises(ValueError):
                ai_models.get_chat_model("unknown")


class ChromaDirTests(unittest.TestCase):
    def test_openai_keeps_original_folder(self):
        with use_provider("openai"):
            self.assertEqual(os.path.basename(ai_models.chroma_dir()), "chroma_db")

    def test_gemini_folder_is_named_after_embedding_model(self):
        with use_provider("gemini"):
            self.assertEqual(
                os.path.basename(ai_models.chroma_dir()),
                "chroma_db_gemini_" + Config.MODELS["gemini"]["embedding"].replace("-", "_"),
            )

    def test_huggingface_folder_is_named_after_embedding_model(self):
        models = {**Config.MODELS, "huggingface": {**Config.MODELS["huggingface"], "embedding": "BAAI/bge-small-en-v1.5"}}
        with use_provider("huggingface"), patch.object(Config, "MODELS", models):
            self.assertEqual(
                os.path.basename(ai_models.chroma_dir()),
                "chroma_db_hf_BAAI_bge_small_en_v1_5",
            )


    def test_ollama_folder_is_named_after_embedding_model(self):
        with use_provider("ollama"):
            self.assertEqual(
                os.path.basename(ai_models.chroma_dir()),
                "chroma_db_ollama_" + Config.MODELS["ollama"]["embedding"].replace("-", "_"),
            )


class HuggingFaceStructuredOutputTests(unittest.TestCase):
    def test_parses_json_reply_and_adds_format_instructions(self):
        captured = []
        fake_llm = RunnableLambda(
            lambda messages: captured.extend(messages)
            or AIMessage(content='```json\n{"value": "ok"}\n```')
        )
        with use_provider("huggingface"), patch.object(
            ai_models, "get_chat_model", return_value=fake_llm
        ):
            model = ai_models.get_structured_model("profile", Answer)
            result = model.invoke([HumanMessage(content="hi")])

        self.assertEqual(result, Answer(value="ok"))
        self.assertIn("JSON", captured[0].content)
        self.assertEqual(captured[1].content, "hi")


class ConfigValidationTests(unittest.TestCase):
    def test_missing_key_for_active_provider_fails(self):
        with patch.multiple(Config, AI_PROVIDER="huggingface", HF_TOKEN=None):
            with self.assertRaises(ValueError):
                Config.validate()
        with patch.multiple(Config, AI_PROVIDER="openai", OPENAI_API_KEY=None):
            with self.assertRaises(ValueError):
                Config.validate()

    def test_ollama_needs_no_api_key(self):
        with patch.multiple(
            Config,
            AI_PROVIDER="ollama",
            OPENAI_API_KEY=None,
            GOOGLE_API_KEY=None,
            HF_TOKEN=None,
            FALLBACK_REASON=None,
        ):
            Config.validate()

    def test_unknown_provider_fails(self):
        with patch.object(Config, "AI_PROVIDER", "not-a-provider"):
            with self.assertRaises(ValueError):
                Config.validate()


def ollama_tags_response(*names):
    body = json.dumps({"models": [{"name": name} for name in names]}).encode()
    return io.BytesIO(body)


class OllamaFallbackTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.multiple(
            Config,
            AI_PROVIDER="ollama",
            REQUESTED_PROVIDER="ollama",
            FALLBACK_REASON=None,
            FALLBACK_PROVIDER="gemini",
            OLLAMA_BASE_URL="http://ollama-host:11434",
            GOOGLE_API_KEY="test-google-key",
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.all_models = sorted(set(Config.MODELS["ollama"].values()))

    def test_stays_on_ollama_when_server_has_every_model(self):
        tags = [name if ":" in name else f"{name}:latest" for name in self.all_models]
        with patch("config.urllib.request.urlopen", return_value=ollama_tags_response(*tags)):
            Config.resolve_provider()
        self.assertEqual(Config.AI_PROVIDER, "ollama")
        self.assertIsNone(Config.FALLBACK_REASON)
        Config.validate()

    def test_falls_back_when_server_is_unreachable(self):
        with patch(
            "config.urllib.request.urlopen",
            side_effect=urllib.error.URLError("refused"),
        ):
            Config.resolve_provider()
        self.assertEqual(Config.AI_PROVIDER, "gemini")
        self.assertEqual(Config.REQUESTED_PROVIDER, "ollama")
        self.assertIn("http://ollama-host:11434", Config.FALLBACK_REASON)
        self.assertEqual(ai_models.provider_status(), ("Google Gemini", Config.FALLBACK_REASON))
        Config.validate()

    def test_falls_back_when_a_model_is_missing(self):
        with patch(
            "config.urllib.request.urlopen",
            return_value=ollama_tags_response(self.all_models[0]),
        ):
            Config.resolve_provider()
        self.assertEqual(Config.AI_PROVIDER, "gemini")
        self.assertIn(self.all_models[-1], Config.FALLBACK_REASON)

    def test_fallback_without_gemini_key_explains_both_problems(self):
        with patch.object(Config, "GOOGLE_API_KEY", None), patch(
            "config.urllib.request.urlopen",
            side_effect=urllib.error.URLError("refused"),
        ):
            Config.resolve_provider()
            with self.assertRaises(ValueError) as raised:
                Config.validate()
        self.assertIn("not reachable", str(raised.exception))
        self.assertIn("GOOGLE_API_KEY", str(raised.exception))

    def test_other_providers_skip_the_check(self):
        with patch.object(Config, "AI_PROVIDER", "openai"), patch(
            "config.urllib.request.urlopen"
        ) as urlopen:
            Config.resolve_provider()
        urlopen.assert_not_called()
        self.assertIsNone(Config.FALLBACK_REASON)


if __name__ == "__main__":
    unittest.main()
