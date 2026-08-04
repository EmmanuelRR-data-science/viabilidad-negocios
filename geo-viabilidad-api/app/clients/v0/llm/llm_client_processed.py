"""LLM provider facade — dispatches on settings.LLM_PROVIDER config.

Providers:
- groq: Groq Cloud API (default for local dev)
- openai: OpenAI-compatible API
- bedrock: AWS Bedrock Runtime (production)

All callers (foda_service, bedrock_client_processed) should use this facade
instead of hard-wiring to a specific provider.
"""

from __future__ import annotations

import json
import logging

from app.clients.v0.llm.llm_client_raw import (
    invocar_bedrock_raw,
    invocar_groq_raw,
    invocar_openai_raw,
)
from app.core.config import settings

logger = logging.getLogger("llm_client_processed")

_PROVIDERS = ("groq", "openai", "bedrock")


def _groq_disponible() -> bool:
    return (
        bool(settings.GROQ_API_KEY)
        and not settings.GROQ_API_KEY.startswith("pega_tu")
        and "tu_token" not in settings.GROQ_API_KEY
    )


def _openai_disponible() -> bool:
    return bool(settings.OPENAI_API_KEY) and not settings.OPENAI_API_KEY.startswith("pega_tu")


def _resolve_provider() -> str:
    """Return the effective provider name, falling back gracefully."""
    prov = settings.LLM_PROVIDER
    if prov not in _PROVIDERS:
        logger.warning("[LLM] settings.LLM_PROVIDER=%r no reconocido; usando 'groq'.", prov)
        prov = "groq"

    if prov == "groq" and _groq_disponible():
        return "groq"
    if prov == "openai" and _openai_disponible():
        return "openai"
    if prov == "bedrock" and settings.AWS_ENABLED and not settings.DEV_MODE:
        return "bedrock"

    if _groq_disponible():
        return "groq"
    if _openai_disponible():
        return "openai"
    if settings.AWS_ENABLED and not settings.DEV_MODE:
        return "bedrock"

    return "none"


def invocar_chat_json(system_prompt: str, user_prompt: str) -> str | None:
    """Invoke the configured LLM and return raw JSON string, or None on failure."""
    provider = _resolve_provider()
    logger.info("[LLM] Usando provider: %s", provider)

    if provider == "groq":
        return invocar_groq_raw(system_prompt, user_prompt, settings.GROQ_API_KEY, settings.GROQ_MODEL)
    elif provider == "openai":
        return invocar_openai_raw(system_prompt, user_prompt, settings.OPENAI_API_KEY, settings.OPENAI_MODEL)
    elif provider == "bedrock":
        return invocar_bedrock_raw(system_prompt, user_prompt, settings.BEDROCK_MODEL_ID)

    logger.warning("[LLM] Sin provider disponible.")
    return None


def invocar_foda_llm_raw(datos_entorno: dict, intenciones: str) -> dict | None:
    """FODA invocation via the provider facade.

    Reuses sanitization and schema validation from bedrock_client_processed,
    but routes the actual LLM call through the provider registry.
    """
    from app.clients.v0.bedrock.bedrock_client_processed import (
        sanitizar_input_usuario,
        validar_schema_foda,
    )

    rubro_raw = datos_entorno.get("rubro", "Giro no especificado")
    rubro = sanitizar_input_usuario(rubro_raw, field="rubro") or "Negocio general"
    intenciones = sanitizar_input_usuario(intenciones, field="intenciones") or "Sin intenciones especiales escritas."

    provider = _resolve_provider()
    if provider == "none":
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

    raw_response = invocar_chat_json(system_prompt, user_prompt)
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
            logger.error("[LLM] Error parseando JSON del provider %s: %s", provider, e)

    return None
