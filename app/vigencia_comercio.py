"""Señales de vigencia operativa de comercios (Google Places + reseñas)."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

_KEYWORDS_CIERRE = (
    "ya cerro",
    "ya cerró",
    "cerraron",
    "cerrado",
    "cerro definitivamente",
    "cerró definitivamente",
    "ya no existe",
    "ya no opera",
    "permanently closed",
    "closed permanently",
    "shut down",
    "out of business",
    "dejo de operar",
    "dejó de operar",
)

_DISCLAIMER_VIGENCIA = (
    "La vigencia operativa se infiere de datos públicos de Google Maps (estado del negocio y "
    "fecha de reseñas recientes). Un alto rating histórico no garantiza que el local siga abierto. "
    "Recomendamos validar en sitio antes de decisiones de inversión."
)


def disclaimer_vigencia() -> str:
    return _DISCLAIMER_VIGENCIA


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", (texto or "").lower().strip())


def detectar_cierre_en_resenas(reseñas: list[dict] | None) -> bool:
    for rev in reseñas or []:
        blob = _normalizar(rev.get("texto", ""))
        if any(kw in blob for kw in _KEYWORDS_CIERRE):
            return True
    return False


def _meses_desde_unix(ts: int | None) -> int | None:
    if not ts or ts <= 0:
        return None
    fecha = dt.datetime.utcfromtimestamp(ts)
    delta = dt.datetime.utcnow() - fecha
    return max(0, int(delta.days / 30))


def evaluar_vigencia_comercio(
    *,
    business_status: str | None = None,
    reseñas_google: list[dict] | None = None,
) -> dict[str, Any]:
    """Calcula nivel de confianza de que el comercio sigue operando."""
    status = (business_status or "UNKNOWN").upper()
    reseñas = list(reseñas_google or [])

    timestamps = [int(r["time"]) for r in reseñas if r.get("time")]
    ultima_unix = max(timestamps) if timestamps else None
    meses = _meses_desde_unix(ultima_unix)
    cierre_en_texto = detectar_cierre_en_resenas(reseñas)

    fecha_ultima = None
    if ultima_unix:
        fecha_ultima = dt.datetime.utcfromtimestamp(ultima_unix).strftime("%Y-%m-%d")

    if status == "CLOSED_PERMANENTLY":
        return {
            "business_status": status,
            "nivel": "inactivo",
            "etiqueta": "Cerrado según Google",
            "lectura": "Google reporta cierre permanente; no se considera competidor o aliado activo.",
            "activo_para_analisis": False,
            "meses_sin_actividad": meses,
            "fecha_ultima_resena": fecha_ultima,
            "cierre_reportado_en_resenas": cierre_en_texto,
        }

    if status == "CLOSED_TEMPORARILY":
        return {
            "business_status": status,
            "nivel": "baja",
            "etiqueta": "Cierre temporal",
            "lectura": "Google indica cierre temporal; valida si reabrió antes de asumir competencia activa.",
            "activo_para_analisis": False,
            "meses_sin_actividad": meses,
            "fecha_ultima_resena": fecha_ultima,
            "cierre_reportado_en_resenas": cierre_en_texto,
        }

    if cierre_en_texto:
        return {
            "business_status": status,
            "nivel": "baja",
            "etiqueta": "Posible cierre",
            "lectura": "Usuarios mencionan cierre en reseñas recientes; confirma en campo si sigue operando.",
            "activo_para_analisis": True,
            "meses_sin_actividad": meses,
            "fecha_ultima_resena": fecha_ultima,
            "cierre_reportado_en_resenas": True,
        }

    if meses is None:
        lectura = (
            "Google no reporta cierre, pero no hay reseñas públicas recientes para confirmar actividad."
            if status == "OPERATIONAL"
            else "Sin estado operativo ni reseñas recientes en Google."
        )
        return {
            "business_status": status,
            "nivel": "media",
            "etiqueta": "Sin señales recientes",
            "lectura": lectura,
            "activo_para_analisis": True,
            "meses_sin_actividad": None,
            "fecha_ultima_resena": None,
            "cierre_reportado_en_resenas": False,
        }

    if meses <= 6:
        return {
            "business_status": status,
            "nivel": "alta",
            "etiqueta": "Actividad reciente",
            "lectura": (
                f"Google lo marca como operativo y la última reseña pública es de hace {meses} mes(es)."
            ),
            "activo_para_analisis": True,
            "meses_sin_actividad": meses,
            "fecha_ultima_resena": fecha_ultima,
            "cierre_reportado_en_resenas": False,
        }

    if meses <= 18:
        return {
            "business_status": status,
            "nivel": "media",
            "etiqueta": "Actividad moderada",
            "lectura": (
                f"Sin cierre reportado, pero la última reseña es de hace {meses} meses; "
                "podría seguir abierto con poca actividad en Google."
            ),
            "activo_para_analisis": True,
            "meses_sin_actividad": meses,
            "fecha_ultima_resena": fecha_ultima,
            "cierre_reportado_en_resenas": False,
        }

    return {
        "business_status": status,
        "nivel": "baja",
        "etiqueta": "Listing posiblemente obsoleto",
        "lectura": (
            f"Alto rating histórico posible, pero sin reseñas nuevas en {meses} meses. "
            "Valida en sitio si el local sigue operando."
        ),
        "activo_para_analisis": True,
        "meses_sin_actividad": meses,
        "fecha_ultima_resena": fecha_ultima,
        "cierre_reportado_en_resenas": False,
    }


def vigencia_sin_verificar() -> dict[str, Any]:
    return {
        "business_status": "UNKNOWN",
        "nivel": "sin_verificar",
        "etiqueta": "Sin verificar",
        "lectura": "No se consultó el detalle operativo en Google para este establecimiento.",
        "activo_para_analisis": True,
        "meses_sin_actividad": None,
        "fecha_ultima_resena": None,
        "cierre_reportado_en_resenas": False,
    }
