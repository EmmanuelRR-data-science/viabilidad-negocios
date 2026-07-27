"""Bedrock adapter — wraps existing bedrock_client_raw AWS calls."""

from __future__ import annotations

import logging

from app.clients.v0.bedrock.bedrock_client_raw import invocar_bedrock_foda_raw
from app.core.config import AWS_ENABLED, BEDROCK_MODEL_ID

logger = logging.getLogger("llm_adapter_bedrock")


class BedrockAdapter:
    def _is_available(self) -> bool:
        return bool(AWS_ENABLED)

    def chat_json(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self._is_available():
            logger.warning("[BEDROCK] AWS not enabled (DEV_MODE?).")
            return None
        return invocar_bedrock_foda_raw(system_prompt, user_prompt, BEDROCK_MODEL_ID)

    def guardrail_check(self, texto: str) -> tuple[bool, str]:
        """Bedrock has no built-in moderation endpoint; always pass."""
        return True, "safe"
