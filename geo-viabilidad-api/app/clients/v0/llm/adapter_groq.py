"""Groq adapter — wraps existing bedrock_client_raw Groq calls."""

from __future__ import annotations

import logging

from app.clients.v0.bedrock.bedrock_client_raw import (
    invocar_groq_foda_raw,
)
from app.core.config import settings

logger = logging.getLogger("llm_adapter_groq")


class GroqAdapter:
    def _is_available(self) -> bool:
        return (
            bool(settings.GROQ_API_KEY)
            and not settings.GROQ_API_KEY.startswith("pega_tu")
            and "tu_token" not in settings.GROQ_API_KEY
        )

    def chat_json(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self._is_available():
            logger.warning("[GROQ] API key not configured.")
            return None
        return invocar_groq_foda_raw(system_prompt, user_prompt, settings.GROQ_API_KEY, settings.GROQ_MODEL)
