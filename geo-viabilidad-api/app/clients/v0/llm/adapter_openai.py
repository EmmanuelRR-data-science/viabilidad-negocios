"""OpenAI adapter — HTTP calls to OpenAI chat completions (same shape as Groq)."""

from __future__ import annotations

import logging

import requests

from app.core.config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger("llm_adapter_openai")


class OpenAIAdapter:
    _URL = "https://api.openai.com/v1/chat/completions"

    def _is_available(self) -> bool:
        return bool(OPENAI_API_KEY) and not OPENAI_API_KEY.startswith("pega_tu")

    def chat_json(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self._is_available():
            logger.warning("[OPENAI] API key not configured.")
            return None

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": OPENAI_MODEL,
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

    def guardrail_check(self, texto: str) -> tuple[bool, str]:
        """OpenAI moderation endpoint (free tier)."""
        if not self._is_available():
            return True, "safe"

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(
                "https://api.openai.com/v1/moderations",
                json={"input": texto},
                headers=headers,
                timeout=10,
            )
            if resp.status_code != 200:
                return True, "safe"
            result = resp.json().get("results", [{}])[0]
            if result.get("flagged"):
                cats = [k for k, v in result.get("categories", {}).items() if v]
                return False, ",".join(cats) or "unsafe"
            return True, "safe"
        except Exception as err:
            logger.warning("[OPENAI] Moderation check failed: %s", err)
            return True, "safe"
