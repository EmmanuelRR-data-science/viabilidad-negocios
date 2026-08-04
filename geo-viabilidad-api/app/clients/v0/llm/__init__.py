"""LLM provider abstraction — dispatches on LLM_PROVIDER env var.

Supported providers: groq (default in DEV), openai, bedrock.
"""

from app.clients.v0.llm.llm_client_processed import (
    invocar_chat_json,
    invocar_foda_llm_raw,
)

invocar_foda_llm = invocar_foda_llm_raw

__all__ = [
    "invocar_chat_json",
    "invocar_foda_llm",
    "invocar_foda_llm_raw",
]
