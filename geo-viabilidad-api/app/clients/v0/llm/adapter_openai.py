"""OpenAI adapter — HTTP calls to OpenAI chat completions (same shape as Groq)."""

from __future__ import annotations

import logging

import requests

from app.core.config import settings

logger = logging.getLogger("llm_adapter_openai")


class OpenAIAdapter:
    _URL = "https://api.openai.com/v1/chat/completions"

    def _is_available(self) -> bool:
        return bool(settings.OPENAI_API_KEY) and not settings.OPENAI_API_KEY.startswith("pega_tu")

    def chat_json(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self._is_available():
            logger.warning("[OPENAI] API key not configured.")
            return None

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        }

        try:
            response = requests.post(self._URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as err:
            logger.error("[OPENAI] Chat Completion failed: %s", err)
            return None
