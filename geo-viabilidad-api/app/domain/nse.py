"""Funciones puras de cálculo NSE — sin I/O, sin Session, sin client imports."""

from __future__ import annotations

import logging

from app.schemas.domain.nse import NSEDiagnostico, NSEMetricasRaw

logger = logging.getLogger("nse")


def hash_nse_fallback(lat: float, lng: float) -> int:
    return int(abs(lat * 1000 + lng * 1000)) % 100


def etiqueta_desde_score(score: float) -> str:
    if score >= 70:
        return "A/B (Alto / Alto Medio)"
    if score >= 55:
        return "C+ (Medio Alto)"
    if score >= 40:
        return "C / C- (Medio / Medio Bajo)"
    if score >= 25:
        return "D+ (Bajo Alto)"
    return "D / E (Bajo / Muy Bajo)"


def nse_score_desde_metricas(escolaridad: float, internet_pct: float, autos_pct: float) -> float:
    return round(
        (escolaridad / 18.0 * 40.0) + (internet_pct * 0.3) + (autos_pct * 0.3),
        1,
    )


def derivar_metricas_fallback(hash_val: int) -> NSEMetricasRaw:
    if hash_val < 10:
        escolaridad, internet, autos, pc = 14.0, 85.0, 70.0, 65.0
    elif hash_val < 35:
        escolaridad, internet, autos, pc = 11.0, 65.0, 45.0, 40.0
    elif hash_val < 70:
        escolaridad, internet, autos, pc = 9.0, 45.0, 30.0, 25.0
    elif hash_val < 90:
        escolaridad, internet, autos, pc = 7.0, 25.0, 15.0, 12.0
    else:
        escolaridad, internet, autos, pc = 5.0, 10.0, 5.0, 5.0
    return {
        "escolaridad_promedio": escolaridad,
        "internet_pct": internet,
        "autos_pct": autos,
        "pc_pct": pc,
        "fuente": "fallback_determinista",
    }


def construir_nse_sin_datos() -> NSEDiagnostico:
    return {
        "nse_score": 0.0,
        "nse_etiqueta": "Sin datos censales",
        "metricas": {
            "escolaridad_promedio": 0.0,
            "internet_pct": 0.0,
            "autos_pct": 0.0,
            "pc_pct": 0.0,
            "fuente": "sin_datos",
        },
        "agebs_consultadas": 0,
    }


def construir_nse_fallback(lat: float, lng: float) -> NSEDiagnostico:
    hash_val = hash_nse_fallback(lat, lng)
    metricas = derivar_metricas_fallback(hash_val)
    score = nse_score_desde_metricas(
        metricas["escolaridad_promedio"],
        metricas["internet_pct"],
        metricas["autos_pct"],
    )
    return {
        "nse_score": score,
        "nse_etiqueta": etiqueta_desde_score(score),
        "metricas": metricas,
        "agebs_consultadas": 0,
    }


def resolver_sin_censo(lat: float, lng: float, *, permitir_fallback_sin_censo: bool) -> NSEDiagnostico:
    if permitir_fallback_sin_censo:
        logger.info("Sin datos censales; usando fallback determinista (modo desarrollo).")
        return construir_nse_fallback(lat, lng)
    logger.info("Sin datos censales en la zona; NSE no disponible (producción).")
    return construir_nse_sin_datos()


def construir_nse_desde_raw(raw: dict) -> NSEDiagnostico:
    """Construye NSEDiagnostico a partir de los datos raw ya consultados por el DB client."""
    escolaridad = raw["escolaridad_promedio"]
    internet = min(100.0, max(0.0, raw["internet_pct"]))
    autos = min(100.0, max(0.0, raw["autos_pct"]))
    pc = min(100.0, max(0.0, raw["pc_pct"]))

    metricas: NSEMetricasRaw = {
        "escolaridad_promedio": round(escolaridad, 1),
        "internet_pct": round(internet, 1),
        "autos_pct": round(autos, 1),
        "pc_pct": round(pc, 1),
        "fuente": "censo_2020",
    }
    score = nse_score_desde_metricas(escolaridad, internet, autos)
    return {
        "nse_score": score,
        "nse_etiqueta": etiqueta_desde_score(score),
        "metricas": metricas,
        "agebs_consultadas": raw["agebs_consultadas"],
    }


def nse_es_bajo(nse: NSEDiagnostico | dict | None) -> bool:
    if not nse:
        return False
    etiqueta = str(nse.get("nse_etiqueta", ""))
    return etiqueta.startswith("D")
