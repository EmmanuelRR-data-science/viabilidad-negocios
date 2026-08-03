"""Orquestación FODA: invoca bedrock client → aplica enrichment narrativo.

Toda la lógica de respaldo cuantitativo, quejas, y narrativa vive aquí (capa servicios).
"""

from __future__ import annotations

import logging

from app.clients.v0.bedrock.bedrock_client_processed import (
    generar_consideraciones_apertura,
    recortar_lista_texto,
)
from app.clients.v0.google.google_giro_filter import competidor_es_relevante_al_giro
from app.clients.v0.llm import invocar_foda_llm as _invocar_foda_llm
from app.domain.aliados_deterministico import etiquetas_aliados_legibles, resolver_aliados_por_rubro
from app.services.presentation.narrative import enriquecer_lista_lectura, generar_conclusion_detallada

logger = logging.getLogger("foda_service")

_LLM_DIAGNOSTICO_KEYS = {"fortalezas", "oportunidades"}


def enriquecer_items_foda(
    items: list[str] | None,
    analisis: dict,
    *,
    max_items: int = 3,
) -> list[str]:
    return enriquecer_lista_lectura(items, analisis, max_items=max_items)


def conclusion_foda_detallada(
    analisis: dict,
    rubro: str,
    *,
    tier: str = "premium",
    radio_metros: int = 1000,
) -> str:
    return generar_conclusion_detallada(analisis, rubro, tier=tier, radio_metros=radio_metros)


def _desc_aliados_matriz(rubro: str, intenciones: str | None = None) -> str:
    tipos = resolver_aliados_por_rubro(rubro, intenciones=intenciones)
    return f"Matriz de geomarketing por rubro ({etiquetas_aliados_legibles(tipos)})"


def _fortalezas_respaldo_detalladas(datos_entorno: dict) -> list[str]:
    poblacion = datos_entorno.get("poblacion_ponderada", 0)
    densidad = datos_entorno.get("densidad_hab_km2", 0)
    competencia = datos_entorno.get("competidores_conteo", 0)
    nse_info = datos_entorno.get("nse") or {}
    nse_etiqueta = nse_info.get("nse_etiqueta", "No disponible")
    metricas = nse_info.get("metricas") or {}

    borrador = [
        f"Base demográfica de {poblacion:,} personas ({densidad:,.1f} hab/km² en el radio analizado).",
        (
            f"NSE {nse_etiqueta} con escolaridad promedio de "
            f"{float(metricas.get('escolaridad_promedio', 0) or 0):.1f} años."
        ),
    ]
    if competencia == 0:
        borrador.append("Sin competidores directos detectados en el radio de influencia contratado.")

    conteos_aliados = {k: v for k, v in (datos_entorno.get("aliados_conteos") or {}).items() if k != "ia_auto"}
    total_atractores = sum(conteos_aliados.values())
    if total_atractores > 0:
        borrador.append(
            f"Índice de atractores: {total_atractores} puntos de interés en {len(conteos_aliados)} categorías."
        )

    afl = datos_entorno.get("afluencia_peatonal") or {}
    if afl.get("status") == "success" and afl.get("dia_pico"):
        borrador.append(f"Afluencia peatonal: día pico {afl.get('dia_pico')} hora {afl.get('hora_pico', 'N/D')}.")

    return enriquecer_items_foda(borrador, datos_entorno, max_items=3)


def _quejas_desde_competencia_real(datos_entorno: dict) -> list[str]:
    rubro = datos_entorno.get("rubro", "Negocio")
    competidores = datos_entorno.get("competidores_listado") or []
    debiles = [
        c
        for c in competidores
        if isinstance(c, dict)
        and float(c.get("rating") or 0) > 0
        and float(c.get("rating") or 5) < 3.8
        and int(c.get("user_ratings_total") or 0) >= 5
        and competidor_es_relevante_al_giro(rubro, c)
    ]
    debiles.sort(key=lambda c: (float(c.get("rating") or 0), -int(c.get("user_ratings_total") or 0)))

    quejas = []
    for comp in debiles[:3]:
        nombre = comp.get("nombre", "Competidor local")
        rating = float(comp.get("rating") or 0)
        resenas = int(comp.get("user_ratings_total") or 0)
        quejas.append(
            f"'{nombre}' registra {rating}/5 con {resenas:,} reseñas en Google Places "
            "— señal de oportunidad para superar su propuesta de valor."
        )
    return quejas


def foda_respaldo_cuantitativo(
    datos_entorno: dict,
    rubro: str,
    *,
    comp_adicionales: str | None = None,
    aliados_adicionales: str | None = None,
) -> dict:
    """Diagnóstico de respaldo basado en métricas reales (sin LLM)."""
    poblacion = datos_entorno.get("poblacion_ponderada", 0)
    direcc = datos_entorno.get("direccion", "Ubicación seleccionada")
    nse_info = datos_entorno.get("nse") or {}
    nse_etiqueta = nse_info.get("nse_etiqueta", "No disponible")
    sva = datos_entorno.get("sva", 50)

    if sva >= 80:
        veredicto_dictamen = "COMERCIALMENTE VIABLE"
    elif sva >= 50:
        veredicto_dictamen = "COMERCIALMENTE ACEPTABLE CON CONDICIONES DE DIFERENCIACIÓN"
    else:
        veredicto_dictamen = "DE ALTO RIESGO OPERATIVO"

    fortalezas_list = _fortalezas_respaldo_detalladas(datos_entorno)
    quejas_reales = _quejas_desde_competencia_real(datos_entorno)

    tier = datos_entorno.get("tier_adquirido") or "premium"
    radio = int(datos_entorno.get("radio_metros") or 1000)
    conclusion_larga = conclusion_foda_detallada(datos_entorno, rubro, tier=tier, radio_metros=radio)

    return {
        "_fuente": "respaldo_cuantitativo",
        "fortalezas": fortalezas_list,
        "oportunidades": [],
        "consideraciones_apertura": generar_consideraciones_apertura(datos_entorno),
        "conclusion": conclusion_larga,
        "segmentacion_nicho": (
            f"Población de {poblacion:,} habitantes en {direcc} con afinidad al giro '{rubro}' "
            f"y NSE predominante {nse_etiqueta}."
        ),
        "dictamen_final": f"Dictamen {veredicto_dictamen} para '{rubro}' en {direcc}, basado en datos INEGI y Places.",
        "top_quejas_competidores": quejas_reales,
    }


def _aplicar_politica_honesta_foda(
    foda_llm: dict,
    datos_entorno: dict,
    rubro: str,
    *,
    comp_adicionales: str | None,
    aliados_adicionales: str | None,
) -> dict:
    """Fusiona fortalezas/oportunidades del LLM con respaldo cuantitativo."""
    respaldo = foda_respaldo_cuantitativo(
        datos_entorno, rubro, comp_adicionales=comp_adicionales, aliados_adicionales=aliados_adicionales
    )
    resultado = {k: v for k, v in respaldo.items() if k != "_fuente"}

    for campo in _LLM_DIAGNOSTICO_KEYS:
        items = recortar_lista_texto(foda_llm.get(campo), max_items=3)
        if items:
            resultado[campo] = enriquecer_items_foda(items, datos_entorno, max_items=3)

    resultado["consideraciones_apertura"] = generar_consideraciones_apertura(datos_entorno)
    tier = datos_entorno.get("tier_adquirido") or "premium"
    radio = int(datos_entorno.get("radio_metros") or 1000)
    resultado["conclusion"] = conclusion_foda_detallada(datos_entorno, rubro, tier=tier, radio_metros=radio)
    return resultado


def generar_analisis_foda(datos_entorno: dict, intenciones: str) -> dict:
    """Orquesta: bedrock client (LLM raw) → enrichment narrativo.

    Retorna el diagnóstico FODA completo listo para el PDF/API.
    """
    from app.clients.v0.bedrock.bedrock_client_processed import sanitizar_input_usuario

    rubro_raw = datos_entorno.get("rubro", "Giro no especificado")
    rubro = sanitizar_input_usuario(rubro_raw, field="rubro") or "Negocio general"
    datos_entorno_sanitizado = {**datos_entorno, "rubro": rubro}

    comp_adicionales = datos_entorno.get("competidores_adicionales")
    aliados_adicionales = datos_entorno.get("aliados_adicionales")

    foda_llm = _invocar_foda_llm(datos_entorno_sanitizado, intenciones)
    if foda_llm is None:
        return foda_respaldo_cuantitativo(
            datos_entorno_sanitizado,
            rubro,
            comp_adicionales=comp_adicionales,
            aliados_adicionales=aliados_adicionales,
        )

    return _aplicar_politica_honesta_foda(
        foda_llm,
        datos_entorno_sanitizado,
        rubro,
        comp_adicionales=comp_adicionales,
        aliados_adicionales=aliados_adicionales,
    )
