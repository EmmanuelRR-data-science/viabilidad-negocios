"""
Selección de atractores de tráfico para dashboard y PDF.

Estándar: pool máximo de 10 candidatos; cantidad mostrada 3, 5, 7 o 10 según
cuántos cumplan calificación Google alta dentro del pool (rating + reseñas mínimas).
"""

from __future__ import annotations

from typing import Any

MAX_POOL_ATRACTORES = 10
MIN_RESENAS_BUENA = 5
RATING_BUENA_DEFAULT = 4.0
RATING_BUENA_PREMIUM = 4.2
TAMANOS_POSIBLES = (3, 5, 7, 10)


def _umbral_rating(tier: str | None) -> float:
    if (tier or "").lower() == "premium":
        return RATING_BUENA_PREMIUM
    return RATING_BUENA_DEFAULT


def _es_buena_calificacion(lugar: dict, *, tier: str | None) -> bool:
    rating = float(lugar.get("rating") or 0)
    resenas = int(lugar.get("user_ratings_total") or 0)
    return rating >= _umbral_rating(tier) and resenas >= MIN_RESENAS_BUENA


def _clave_lugar(lugar: dict) -> tuple:
    lat = lugar.get("latitud")
    lng = lugar.get("longitud")
    if lat is not None and lng is not None:
        return ("coords", round(float(lat), 5), round(float(lng), 5))
    return ("nombre", (lugar.get("nombre") or "").strip().lower())


def _sort_key(lugar: dict) -> tuple:
    resenas = int(lugar.get("user_ratings_total") or 0)
    rating = float(lugar.get("rating") or 0)
    muestra_confiable = resenas >= MIN_RESENAS_BUENA
    return (
        1 if muestra_confiable else 0,
        rating,
        resenas,
        -float(lugar.get("distancia_metros") or 99999.0),
    )


def _tamano_segun_calidad(n_buenos: int) -> int:
    """Mapea cuántos atractores 'buenos' hay en el pool a 3, 5, 7 o 10 filas."""
    if n_buenos >= 8:
        return 10
    if n_buenos >= 6:
        return 7
    if n_buenos >= 4:
        return 5
    return 3


def seleccionar_atractores_destacados(
    aliados: list[dict],
    *,
    tier: str | None = None,
) -> tuple[list[dict], dict[str, Any]]:
    """
    Devuelve la lista curada para PDF/dashboard (máx. 10) y metadatos de la regla aplicada.

    Prioridad de ranking: muestra confiable (≥5 reseñas) → rating → reseñas → cercanía.
    'Buena calificación': rating ≥ 4.0 (Pro/Básico) o ≥ 4.2 (Premium) y ≥ 5 reseñas en Google.
    """
    umbral = _umbral_rating(tier)
    if not aliados:
        return [], {
            "cantidad_mostrada": 0,
            "cantidad_detectada": 0,
            "limite_maximo": MAX_POOL_ATRACTORES,
            "calificacion_minima_buena": umbral,
            "resenas_minimas_buena": MIN_RESENAS_BUENA,
            "tier_aplicado": tier or "pro",
            "atractores_calificacion_alta_en_pool": 0,
            "tamano_aplicado": 0,
            "regla": "Sin atractores detectados en el radio.",
        }

    ordenados = sorted(aliados, key=_sort_key, reverse=True)
    pool = ordenados[:MAX_POOL_ATRACTORES]
    buenos = [a for a in pool if _es_buena_calificacion(a, tier=tier)]
    n_buenos = len(buenos)
    n_mostrar = min(_tamano_segun_calidad(n_buenos), len(ordenados))

    seleccionados: list[dict] = []
    vistos: set[tuple] = set()

    for candidato in buenos:
        if len(seleccionados) >= n_mostrar:
            break
        clave = _clave_lugar(candidato)
        if clave in vistos:
            continue
        vistos.add(clave)
        seleccionados.append(candidato)

    for candidato in pool:
        if len(seleccionados) >= n_mostrar:
            break
        clave = _clave_lugar(candidato)
        if clave in vistos:
            continue
        vistos.add(clave)
        seleccionados.append(candidato)

    tier_label = (tier or "pro").capitalize()
    regla = (
        f"De {len(aliados)} detectados, pool top {len(pool)} por calificación y reseñas; "
        f"{n_buenos} cumplen rating ≥ {umbral:g} con al menos {MIN_RESENAS_BUENA} reseñas "
        f"(umbral {tier_label}) → se muestran {len(seleccionados)} "
        f"(estándar {n_mostrar}, máximo {MAX_POOL_ATRACTORES})."
    )

    return seleccionados, {
        "cantidad_mostrada": len(seleccionados),
        "cantidad_detectada": len(aliados),
        "limite_maximo": MAX_POOL_ATRACTORES,
        "calificacion_minima_buena": umbral,
        "resenas_minimas_buena": MIN_RESENAS_BUENA,
        "tier_aplicado": tier or "pro",
        "atractores_calificacion_alta_en_pool": n_buenos,
        "tamano_aplicado": n_mostrar,
        "regla": regla,
    }
