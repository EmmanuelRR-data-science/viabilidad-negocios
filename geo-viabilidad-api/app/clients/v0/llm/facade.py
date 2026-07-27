"""Provider-agnostic LLM facade.

Routes ``invocar_chat_json`` / ``invocar_foda_llm`` through the adapter
selected by ``LLM_PROVIDER`` (groq | openai | bedrock).
"""

from __future__ import annotations

import logging
from typing import Protocol

from app.core.config import LLM_PROVIDER

logger = logging.getLogger("llm_facade")


class LLMAdapter(Protocol):
    """Minimal contract every LLM adapter must satisfy."""

    def chat_json(self, system_prompt: str, user_prompt: str) -> str | None:
        """Return raw JSON string from the model, or None on failure."""
        ...

    def guardrail_check(self, texto: str) -> tuple[bool, str]:
        """Return (is_safe, category)."""
        ...


def _get_adapter() -> LLMAdapter:
    """Lazy-load the adapter matching ``LLM_PROVIDER``."""
    provider = LLM_PROVIDER
    if provider == "groq":
        from app.clients.v0.llm.adapter_groq import GroqAdapter

        return GroqAdapter()
    if provider == "openai":
        from app.clients.v0.llm.adapter_openai import OpenAIAdapter

        return OpenAIAdapter()
    if provider == "bedrock":
        from app.clients.v0.llm.adapter_bedrock import BedrockAdapter

        return BedrockAdapter()
    logger.warning("LLM_PROVIDER=%r not recognised; falling back to groq.", provider)
    from app.clients.v0.llm.adapter_groq import GroqAdapter

    return GroqAdapter()


def invocar_chat_json(system_prompt: str, user_prompt: str) -> str | None:
    """Send a chat completion request and return the raw JSON string."""
    adapter = _get_adapter()
    return adapter.chat_json(system_prompt, user_prompt)


def invocar_foda_llm(datos_entorno: dict, intenciones: str) -> dict | None:
    """High-level FODA invocation through the selected provider.

    Re-uses the prompt-building and validation logic from
    ``bedrock_client_processed`` but routes the actual LLM call through
    the facade adapter.
    """
    import json

    from app.clients.v0.bedrock.bedrock_client_processed import (
        sanitizar_input_usuario,
        validar_schema_foda,
    )

    rubro_raw = datos_entorno.get("rubro", "Giro no especificado")
    rubro = sanitizar_input_usuario(rubro_raw, field="rubro") or "Negocio general"
    intenciones = sanitizar_input_usuario(intenciones, field="intenciones") or "Sin intenciones especiales escritas."

    adapter = _get_adapter()

    texto_a_guardar = f"Rubro: {rubro}. Intenciones: {intenciones}"
    es_seguro, _ = adapter.guardrail_check(texto_a_guardar)
    if not es_seguro:
        logger.warning("[GUARDRAIL] Input bloqueado por moderación.")
        return None

    poblacion = datos_entorno.get("poblacion_ponderada", 0)
    competencia = datos_entorno.get("competidores_conteo", 0)
    sva = datos_entorno.get("sva", 50)
    direcc = datos_entorno.get("direccion", "Ubicación seleccionada")
    densidad_ctx = datos_entorno.get("densidad_hab_km2", 0)
    nse_info = datos_entorno.get("nse") or {}
    nse_etiqueta_ctx = nse_info.get("nse_etiqueta", "No disponible")

    system_prompt = (
        "Eres un consultor de geomarketing en México. Responde SOLO JSON válido en español con exactamente:\n"
        "{\n"
        '  "fortalezas": ["exactamente 3 bullets"],\n'
        '  "oportunidades": ["exactamente 3 bullets"]\n'
        "}\n"
        "REGLAS:\n"
        "- Exactamente 3 ítems por lista, máximo 200 caracteres cada uno.\n"
        "- Cada bullet debe ser una oración completa: dato + qué significa para el negocio.\n"
        "- Tono descriptivo u orientativo; sin lenguaje de amenaza, debilidad ni predicción de fracaso/éxito.\n"
        "- PROHIBIDO: montos en pesos, porcentajes inventados, nombres de personas.\n"
        "- PROHIBIDO citar el número de competidores como fortaleza.\n"
        "No agregues texto fuera del JSON."
    )

    user_prompt = (
        f"Giro del negocio: {rubro}\n"
        f"Ubicación: {direcc}\n"
        f"Radio de análisis: {datos_entorno.get('radio_metros', 1000)} metros\n"
        f"Población estimada en zona: {poblacion:,} habitantes\n"
        f"Densidad en el radio: {densidad_ctx:,.1f} hab/km²\n"
        f"Número de competidores directos: {competencia} comercios\n"
        f"Score SVA de Viabilidad General: {sva}/100\n"
        f"Nivel socioeconómico (NSE) del radio: {nse_etiqueta_ctx}\n"
        f"Intenciones del emprendedor: {intenciones}\n\n"
        f"Genera fortalezas y oportunidades del punto para el giro '{rubro}' en México."
    )

    raw_response = adapter.chat_json(system_prompt, user_prompt)
    if raw_response:
        try:
            start_idx = raw_response.find("{")
            end_idx = raw_response.rfind("}")
            if start_idx != -1 and end_idx != -1:
                foda_raw = json.loads(raw_response[start_idx : end_idx + 1])
            else:
                foda_raw = json.loads(raw_response)
            return validar_schema_foda(foda_raw)
        except Exception as e:
            logger.error("[LLM FACADE] Error parseando JSON: %s", e)

    return None
