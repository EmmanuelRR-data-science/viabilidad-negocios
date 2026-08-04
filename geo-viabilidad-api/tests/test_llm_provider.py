"""Tests for LLM provider abstraction (clients/v0/llm)."""

import os

os.environ["DEV_MODE"] = "true"

from unittest.mock import patch

from app.clients.v0.llm.llm_client_processed import _resolve_provider, invocar_chat_json


class TestProviderResolution:
    def test_groq_default_in_dev(self):
        with (
            patch("app.core.config.settings.LLM_PROVIDER", "groq"),
            patch("app.core.config.settings.GROQ_API_KEY", "valid_key"),
            patch("app.core.config.settings.DEV_MODE", True),
        ):
            assert _resolve_provider() == "groq"

    def test_openai_when_configured(self):
        with (
            patch("app.core.config.settings.LLM_PROVIDER", "openai"),
            patch("app.core.config.settings.OPENAI_API_KEY", "sk-test"),
            patch("app.core.config.settings.GROQ_API_KEY", ""),
        ):
            assert _resolve_provider() == "openai"

    def test_bedrock_in_prod(self):
        with (
            patch("app.core.config.settings.LLM_PROVIDER", "bedrock"),
            patch("app.core.config.settings.AWS_ENABLED", True),
            patch("app.core.config.settings.DEV_MODE", False),
            patch("app.core.config.settings.GROQ_API_KEY", ""),
        ):
            assert _resolve_provider() == "bedrock"

    def test_fallback_to_groq_when_openai_unavailable(self):
        with (
            patch("app.core.config.settings.LLM_PROVIDER", "openai"),
            patch("app.core.config.settings.OPENAI_API_KEY", ""),
            patch("app.core.config.settings.GROQ_API_KEY", "valid_key"),
        ):
            assert _resolve_provider() == "groq"

    def test_none_when_no_provider_available(self):
        with (
            patch("app.core.config.settings.LLM_PROVIDER", "groq"),
            patch("app.core.config.settings.GROQ_API_KEY", ""),
            patch("app.core.config.settings.OPENAI_API_KEY", ""),
            patch("app.core.config.settings.AWS_ENABLED", False),
            patch("app.core.config.settings.DEV_MODE", True),
        ):
            assert _resolve_provider() == "none"


class TestInvocarChatJson:
    def test_dispatches_to_groq(self):
        with (
            patch("app.clients.v0.llm.llm_client_processed._resolve_provider", return_value="groq"),
            patch(
                "app.clients.v0.llm.llm_client_processed.invocar_groq_raw", return_value='{"test": true}'
            ) as mock_groq,
        ):
            result = invocar_chat_json("system", "user")
            assert result == '{"test": true}'
            mock_groq.assert_called_once()

    def test_dispatches_to_openai(self):
        with (
            patch("app.clients.v0.llm.llm_client_processed._resolve_provider", return_value="openai"),
            patch("app.clients.v0.llm.llm_client_processed.invocar_openai_raw", return_value='{"ok": 1}') as mock_oai,
        ):
            result = invocar_chat_json("system", "user")
            assert result == '{"ok": 1}'
            mock_oai.assert_called_once()

    def test_returns_none_when_no_provider(self):
        with patch("app.clients.v0.llm.llm_client_processed._resolve_provider", return_value="none"):
            assert invocar_chat_json("system", "user") is None


class TestFodaLlmFacade:
    def test_foda_uses_facade(self):
        from app.clients.v0.llm import invocar_foda_llm

        datos = {"rubro": "cafetería", "poblacion_ponderada": 5000, "competidores_conteo": 3, "sva": 70}
        with patch(
            "app.clients.v0.llm.llm_client_processed.invocar_chat_json",
            return_value='{"fortalezas": ["f1", "f2", "f3"], "oportunidades": ["o1"]}',
        ):
            result = invocar_foda_llm(datos, "quiero abrir una cafetería")
            assert result is not None
            assert "fortalezas" in result
