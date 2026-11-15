import os
import unittest
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
    )


class ModelSelectionTests(unittest.TestCase):
    def test_every_task_uses_the_name_from_config(self):
        for provider in ("openai", "gemini", "huggingface"):
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

    def test_unknown_provider_fails(self):
        with patch.object(Config, "AI_PROVIDER", "not-a-provider"):
            with self.assertRaises(ValueError):
                Config.validate()


if __name__ == "__main__":
    unittest.main()
