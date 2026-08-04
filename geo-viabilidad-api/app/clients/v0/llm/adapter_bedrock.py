"""Bedrock adapter — wraps existing bedrock_client_raw AWS calls."""

from __future__ import annotations

import logging

from app.clients.v0.bedrock.bedrock_client_raw import invocar_bedrock_foda_raw
from app.core.config import settings

logger = logging.getLogger("llm_adapter_bedrock")


class BedrockAdapter:
    def _is_available(self) -> bool:
        return bool(settings.AWS_ENABLED)

    def chat_json(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self._is_available():
            logger.warning("[BEDROCK] AWS not enabled (settings.DEV_MODE?).")
            return None
        return invocar_bedrock_foda_raw(system_prompt, user_prompt, settings.BEDROCK_MODEL_ID)
