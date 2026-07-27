"""Groq adapter — wraps existing bedrock_client_raw Groq calls."""

from __future__ import annotations

import logging

from app.clients.v0.bedrock.bedrock_client_raw import (
    invocar_groq_foda_raw,
    verificar_guardrail_groq_raw,
)
from app.core.config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger("llm_adapter_groq")


class GroqAdapter:
    def _is_available(self) -> bool:
        return bool(GROQ_API_KEY) and not GROQ_API_KEY.startswith("pega_tu") and "tu_token" not in GROQ_API_KEY

    def chat_json(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self._is_available():
            logger.warning("[GROQ] API key not configured.")
            return None
        return invocar_groq_foda_raw(system_prompt, user_prompt, GROQ_API_KEY, GROQ_MODEL)

    def guardrail_check(self, texto: str) -> tuple[bool, str]:
        if not self._is_available():
            return True, "safe"
        return verificar_guardrail_groq_raw(texto, GROQ_API_KEY)
