"""Raw LLM provider implementations — HTTP calls only, no business logic."""

from __future__ import annotations

import json
import logging

import requests

from app.core.config import AWS_REGION

logger = logging.getLogger("llm_client_raw")


def invocar_groq_raw(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    model: str,
) -> str | None:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as err:
        logger.error("[RAW] Groq Chat Completion falló: %s", err)
        return None


def invocar_openai_raw(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    model: str,
) -> str | None:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as err:
        logger.error("[RAW] OpenAI Chat Completion falló: %s", err)
        return None


def invocar_bedrock_raw(
    system_prompt: str,
    user_prompt: str,
    model_id: str,
) -> str | None:
    try:
        import boto3

        bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        full_prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n{user_prompt}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        body_json = {"prompt": full_prompt, "max_gen_len": 1500, "temperature": 0.3, "top_p": 0.9}
        response = bedrock.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body_json),
        )
        response_body = json.loads(response.get("body").read())
        return response_body.get("generation", "").strip()
    except Exception as err:
        logger.error("[RAW] AWS Bedrock Runtime falló: %s", err)
        return None


GROQ_GUARD_MODEL = "openai/gpt-oss-safeguard-20b"


def verificar_guardrail_groq_raw(texto_usuario: str, api_key: str) -> tuple[bool, str]:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_GUARD_MODEL,
        "messages": [{"role": "user", "content": texto_usuario}],
        "temperature": 0.0,
        "max_tokens": 20,
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code != 200:
            return True, "safe"
        content = response.json()["choices"][0]["message"]["content"].strip().lower()
        if content.startswith("unsafe"):
            parts = content.split("\n")
            categoria = parts[1].strip() if len(parts) > 1 else "unsafe"
            return False, categoria
        return True, "safe"
    except requests.exceptions.Timeout as err:
        logger.warning("[RAW] Timeout en moderación Llama Guard: %s", err)
        return True, "timeout"
    except Exception as err:
        logger.warning("[RAW] Error al verificar moderación Llama Guard: %s", err)
        return True, "error"
