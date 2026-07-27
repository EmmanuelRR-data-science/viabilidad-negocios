"""Bedrock client processed: sanitización, guardrail, invocación LLM, validación schema.

NO importa app.services — el enrichment/FODA se aplica en la capa de servicios.
"""

from __future__ import annotations

import json
import logging
import re

from app.clients.v0.bedrock.bedrock_client_raw import (
    invocar_bedrock_foda_raw,
    invocar_groq_foda_raw,
    verificar_guardrail_groq_raw,
)
from app.core.config import (
    AWS_ENABLED,
    BEDROCK_MODEL_ID,
    DEV_MODE,
    GROQ_API_KEY,
    GROQ_MODEL,
)

logger = logging.getLogger("bedrock_client_processed")

_MAX_LEN_INTENCIONES = 500
_MAX_LEN_RUBRO = 100
_LLM_DIAGNOSTICO_KEYS = {"fortalezas", "oportunidades"}

_MALICIOUS_PATTERNS = [
    re.compile(r"<\|[a-z_]+\|>", re.IGNORECASE),
    re.compile(r"ignora\s+(todas?\s+)?(las?\s+)?instrucciones", re.IGNORECASE),
    re.compile(r"ignora\s+(todo\s+)?lo\s+anterior", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?previous\s+text", re.IGNORECASE),
    re.compile(r"ignore\s+(everything\s+)?before", re.IGNORECASE),
    re.compile(r"olvida\s+(todo\s+)?lo\s+anterior", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all|previous)", re.IGNORECASE),
    re.compile(r"\bDAN\b"),
    re.compile(r"sin\s+restricciones", re.IGNORECASE),
    re.compile(r"modo\s+(desarrollador|developer|debug)", re.IGNORECASE),
    re.compile(r"\[SYSTEM\s+OVERRIDE\]", re.IGNORECASE),
    re.compile(r"NUEVO\s+PROMPT\s+DE\s+SISTEMA", re.IGNORECASE),
    re.compile(r"NUEVO\s+SISTEMA", re.IGNORECASE),
    re.compile(r"^\s*---\s*$", re.MULTILINE),
    re.compile(r"^#+\s*(NUEVO|NEW|SYSTEM|OVERRIDE|INSTRUCCION)", re.MULTILINE | re.IGNORECASE),
    re.compile(r"system[_\s]*prompt", re.IGNORECASE),
    re.compile(r"prompt\s+de\s+sistema", re.IGNORECASE),
    re.compile(r"variables?\s+de\s+entorno", re.IGNORECASE),
    re.compile(r"env[_\s]*vars?", re.IGNORECASE),
    re.compile(r"GROQ_API_KEY", re.IGNORECASE),
    re.compile(r"AWS_ACCESS_KEY", re.IGNORECASE),
    re.compile(r"DATABASE_URL", re.IGNORECASE),
    re.compile(r"MERCADOPAGO", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"<<SYS>>", re.IGNORECASE),
    re.compile(r"postgresql", re.IGNORECASE),
    re.compile(r"base\s+de\s+datos", re.IGNORECASE),
    re.compile(r"nombres?\s+de\s+las?\s+tablas", re.IGNORECASE),
    re.compile(r"columnas?\s+de\s+las?\s+tablas", re.IGNORECASE),
]


def sanitizar_input_usuario(texto: str | None, *, field: str = "intenciones") -> str | None:
    if not texto or not isinstance(texto, str):
        return None
    max_len = _MAX_LEN_RUBRO if field == "rubro" else _MAX_LEN_INTENCIONES
    texto_truncado = texto[:max_len]
    for pattern in _MALICIOUS_PATTERNS:
        if pattern.search(texto_truncado):
            logger.warning(
                "[SEGURIDAD] Input malicioso detectado en campo '%s'. Patrón: '%s'. Input rechazado.",
                field,
                pattern.pattern[:60],
            )
            return None
    return texto_truncado


def verificar_guardrail_groq(texto_usuario: str, api_key: str) -> tuple[bool, str]:
    return verificar_guardrail_groq_raw(texto_usuario, api_key)


def validar_schema_foda(respuesta: dict) -> dict:
    if not isinstance(respuesta, dict):
        logger.warning("[SEGURIDAD] Respuesta del LLM no es un dict. Schema inválido.")
        return {}
    sanitizada = {k: v for k, v in respuesta.items() if k in _LLM_DIAGNOSTICO_KEYS}
    for campo in ("fortalezas", "oportunidades"):
        if campo in sanitizada and not isinstance(sanitizada[campo], list):
            sanitizada[campo] = [str(sanitizada[campo])]
    return sanitizada


def recortar_lista_texto(items: list | None, *, max_items: int = 3) -> list[str]:
    if not items:
        return []
    resultado = []
    for raw in items:
        texto = str(raw).strip()
        if texto:
            resultado.append(texto)
        if len(resultado) >= max_items:
            break
    return resultado


def generar_consideraciones_apertura(datos_entorno: dict) -> list[str]:
    """Tres consideraciones operativas derivadas de métricas (sin LLM, sin servicio)."""
    sva = int(datos_entorno.get("sva", 50))
    competencia = int(datos_entorno.get("competidores_conteo", 0))
    score_demog = float(datos_entorno.get("score_demog", 50))
    densidad = float(datos_entorno.get("densidad_hab_km2", 0))
    afl = datos_entorno.get("afluencia_peatonal") or {}

    if sva < 50:
        c_sva = "El Score SVA es bajo: define una propuesta de valor claramente diferenciada antes de comprometer inversión."
    elif sva < 80:
        c_sva = "Viabilidad moderada (SVA intermedio): compite por experiencia y servicio, no solo por precio."
    else:
        c_sva = "Aun con SVA favorable, valida costos reales de operación y renta con tu plan de negocio."

    if competencia == 0:
        c_comp = "Sin competidores directos en el radio: establece un estándar de servicio antes de que entren nuevos players."
    elif competencia >= 5:
        c_comp = (
            f"Hay {competencia} competidores activos: visita locales cercanos y contrasta tu oferta con la de ellos."
        )
    else:
        c_comp = f"Con {competencia} competidor(es) en la zona, revisa precios, horarios y reseñas para ubicar tu diferenciador."

    if score_demog < 50 or densidad < 500:
        c_extra = (
            "Mercado residencial acotado en el radio: modela ticket promedio y frecuencia de compra con cifras locales."
        )
    elif afl.get("status") != "success":
        c_extra = "Sin telemetría de afluencia en la zona: valida en sitio el flujo peatonal y los horarios pico."
    else:
        c_extra = "Confirma uso de suelo, permisos del giro y condiciones del local antes de firmar contrato de renta."

    return [c_sva, c_comp, c_extra]


def invocar_foda_llm_raw(datos_entorno: dict, intenciones: str) -> dict | None:
    """Invoca Groq/Bedrock y retorna el JSON sanitizado del LLM, o None si falla.

    NO aplica enrichment ni narrativa — eso lo hace foda_service.
    """
    rubro_raw = datos_entorno.get("rubro", "Giro no especificado")
    rubro = sanitizar_input_usuario(rubro_raw, field="rubro") or "Negocio general"
    intenciones = sanitizar_input_usuario(intenciones, field="intenciones") or "Sin intenciones especiales escritas."

    groq_disponible = bool(GROQ_API_KEY) and not GROQ_API_KEY.startswith("pega_tu") and "tu_token" not in GROQ_API_KEY
    if not groq_disponible:
        return None

    texto_a_guardar = f"Rubro: {rubro}. Intenciones: {intenciones}"
    es_seguro, _ = verificar_guardrail_groq(texto_a_guardar, GROQ_API_KEY)
    if not es_seguro:
        logger.warning("[GUARDRAIL] Input bloqueado por Llama Guard.")
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

    raw_response = invocar_groq_foda_raw(system_prompt, user_prompt, GROQ_API_KEY, GROQ_MODEL)
    if raw_response:
        try:
            foda_raw = json.loads(raw_response)
            return validar_schema_foda(foda_raw)
        except Exception as e:
            logger.error("[LLM] Error parseando Groq JSON: %s", e)

    if DEV_MODE or not AWS_ENABLED:
        return None

    raw_response = invocar_bedrock_foda_raw(system_prompt, user_prompt, BEDROCK_MODEL_ID)
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
            logger.error("[LLM] Error parseando Bedrock JSON: %s", e)

    return None


def determinar_categorias_ia(
    rubro: str,
    *,
    intenciones: str | None = None,
    google_type: str | None = None,
    categoria: str | None = None,
    competidores_adicionales: str | None = None,
) -> dict:
    rub_sanitizado = sanitizar_input_usuario(rubro, field="rubro") or rubro
    int_sanitizado = sanitizar_input_usuario(intenciones, field="intenciones")
    rub_lower = rub_sanitizado.lower()

    fallbacks = {
        "cafe": {"competidores": ["cafe", "bakery"], "aliados": ["school", "transit_station", "shopping_mall", "bank"]},
        "cafeteria": {
            "competidores": ["cafe", "bakery"],
            "aliados": ["school", "transit_station", "shopping_mall", "bank"],
        },
        "comida": {
            "competidores": ["restaurant", "fast_food", "cafe"],
            "aliados": ["transit_station", "shopping_mall", "school", "park"],
        },
        "restaurante": {
            "competidores": ["restaurant", "fast_food"],
            "aliados": ["transit_station", "shopping_mall", "bank", "park"],
        },
        "gym": {"competidores": ["gym"], "aliados": ["pharmacy", "supermarket", "beauty_salon", "transit_station"]},
        "gimnasio": {
            "competidores": ["gym"],
            "aliados": ["pharmacy", "supermarket", "beauty_salon", "transit_station"],
        },
        "farmacia": {
            "competidores": ["pharmacy"],
            "aliados": ["doctor", "supermarket", "convenience_store", "transit_station"],
        },
        "panaderia": {"competidores": ["bakery", "cafe"], "aliados": ["supermarket", "school", "transit_station"]},
        "ropa": {"competidores": ["clothing_store"], "aliados": ["shopping_mall", "beauty_salon", "bank"]},
        "zapateria": {"competidores": ["shoe_store"], "aliados": ["shopping_mall", "clothing_store", "bank"]},
        "supermercado": {
            "competidores": ["supermarket", "convenience_store"],
            "aliados": ["bank", "transit_station", "pharmacy"],
        },
        "floreria": {"competidores": ["store"], "aliados": ["shopping_mall", "school", "doctor", "restaurant"]},
        "flor": {"competidores": ["store"], "aliados": ["shopping_mall", "school", "doctor", "restaurant"]},
    }

    sugerencia_fallback = {"competidores": ["restaurant"], "aliados": ["transit_station", "school", "bank"]}
    for key, val in fallbacks.items():
        if key in rub_lower:
            sugerencia_fallback = val
            break

    system_prompt = (
        "Consulte un rubro comercial y determine categorías de competidores y aliados comerciales.\n"
        "Categorías permitidas:\n"
        '["cafe", "restaurant", "fast_food", "gym", "pharmacy", "bakery", "beauty_salon", '
        '"laundry", "doctor", "bank", "school", "transit_station", "supermarket", '
        '"shopping_mall", "convenience_store", "park", "store", "establishment"]\n\n'
        "Responda estrictamente en JSON:\n"
        '{\n  "competidores": ["categoria1"],\n  "aliados": ["categoria2"]\n}'
    )

    partes_usuario = [
        f"Giro comercial del usuario: '{rub_sanitizado}'",
        f"Mapeo interno sugerido del sistema: tipo '{google_type or 'N/D'}' / categoría '{categoria or 'N/D'}'",
    ]
    if int_sanitizado:
        partes_usuario.append(f"Intenciones y contexto del negocio: '{int_sanitizado}'")
    if competidores_adicionales:
        partes_usuario.append(f"Marcas o competidores mencionados por el usuario: '{competidores_adicionales}'")
    partes_usuario.append("Determina categorías de competidores y aliados.")
    user_prompt = "\n".join(partes_usuario)

    groq_disponible = bool(GROQ_API_KEY) and not GROQ_API_KEY.startswith("pega_tu") and "tu_token" not in GROQ_API_KEY
    if groq_disponible:
        try:
            raw_content = invocar_groq_foda_raw(system_prompt, user_prompt, GROQ_API_KEY, GROQ_MODEL)
            if raw_content:
                res = json.loads(raw_content)
                return filtrar_y_validar_categorias(res, sugerencia_fallback)
        except Exception as e:
            logger.error("[GROQ-CATEGORIAS] Error: %s", e)

    if DEV_MODE or not AWS_ENABLED:
        return sugerencia_fallback

    try:
        raw_content = invocar_bedrock_foda_raw(system_prompt, user_prompt, BEDROCK_MODEL_ID)
        if raw_content:
            start_idx = raw_content.find("{")
            end_idx = raw_content.rfind("}")
            if start_idx != -1 and end_idx != -1:
                res = json.loads(raw_content[start_idx : end_idx + 1])
                return filtrar_y_validar_categorias(res, sugerencia_fallback)
    except Exception as e:
        logger.error("[BEDROCK-CATEGORIAS] Error: %s", e)

    return sugerencia_fallback


def filtrar_y_validar_categorias(res: dict, fallback: dict) -> dict:
    categorias_permitidas = {
        "cafe",
        "restaurant",
        "fast_food",
        "gym",
        "pharmacy",
        "bakery",
        "beauty_salon",
        "laundry",
        "doctor",
        "bank",
        "school",
        "transit_station",
        "supermarket",
        "shopping_mall",
        "convenience_store",
        "park",
        "store",
        "establishment",
    }
    comps = [c for c in res.get("competidores", []) if c in categorias_permitidas]
    aliados = [a for a in res.get("aliados", []) if a in categorias_permitidas]
    return {
        "competidores": comps or fallback.get("competidores", ["restaurant"]),
        "aliados": aliados or fallback.get("aliados", ["transit_station"]),
    }
