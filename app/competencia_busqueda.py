"""Resolución de categorías y palabras clave para búsqueda de competidores/aliados."""

from __future__ import annotations

import unicodedata

# Texto placeholder del checkout cuando el usuario deja intenciones vacías — no sirve como keyword.
_INTENCIONES_PLACEHOLDER = (
    "evaluación comercial del giro en la zona residencial mexicana",
    "evaluacion comercial del giro en la zona residencial mexicana",
)


def contexto_giro_completo(rubro: str, intenciones: str | None = None) -> str:
    """Texto unificado para filtrar relevancia de giro (rubro + intenciones)."""
    r = (rubro or "").strip()
    i = (intenciones or "").strip()
    if r and i:
        return f"{r}. {i}"
    return r or i


def _categorias_manuales(seleccion: list[str] | None) -> list[str]:
    return [c for c in (seleccion or []) if c != "ia_auto"]


def _intenciones_utiles_para_keyword(intenciones: str | None) -> str | None:
    """Frases cortas y específicas del usuario; ignora placeholders genéricos."""
    if not intenciones:
        return None
    limpio = intenciones.strip()
    if not limpio or len(limpio) > 60:
        return None
    norm = unicodedata.normalize("NFKD", limpio)
    norm = "".join(ch for ch in norm if not unicodedata.combining(ch)).lower()
    for placeholder in _INTENCIONES_PLACEHOLDER:
        if placeholder in norm:
            return None
    return limpio


def keyword_places_para_ia(
    rubro: str,
    *,
    intenciones: str | None = None,
    competidores_adicionales: str | None = None,
    google_type: str = "store",
) -> str | None:
    """Palabra clave corta para Nearby Search: rubro primero, sin frases largas de intenciones."""
    if competidores_adicionales:
        primera = competidores_adicionales.split(",")[0].strip()
        if primera:
            return primera[:80]

    rubro_kw = (rubro or "").strip()
    extra = _intenciones_utiles_para_keyword(intenciones)
    if rubro_kw and extra:
        rubro_norm = rubro_kw.lower()
        extra_norm = extra.lower()
        if extra_norm.startswith(rubro_norm):
            extra = extra[len(rubro_kw) :].lstrip(" .,;:-")
        if extra and extra.lower() not in rubro_norm:
            return f"{rubro_kw} {extra}"[:100]
    if rubro_kw:
        return rubro_kw[:80]

    if google_type in ("store", "establishment") and extra:
        return extra[:80]
    return None


def buscar_competidores_ia_con_reintento(
    lat: float,
    lng: float,
    radio: float,
    google_type: str,
    *,
    rubro: str,
    keyword: str | None,
) -> list:
    """Reintenta sin keyword o solo con rubro si Places devuelve cero resultados."""
    from app.google_places import buscar_competidores

    found = buscar_competidores(lat, lng, radio, google_type, keyword=keyword)
    if found:
        return found

    rubro_kw = (rubro or "").strip()[:80] or None
    if keyword and rubro_kw and keyword != rubro_kw:
        found = buscar_competidores(lat, lng, radio, google_type, keyword=rubro_kw)
        if found:
            return found

    if keyword:
        return buscar_competidores(lat, lng, radio, google_type, keyword=None)
    return []


def resolver_tipos_competidores_busqueda(
    competidores_seleccionados: list[str] | None,
    *,
    rubro: str,
    google_type: str,
    categorias_ia: dict,
) -> tuple[list[str] | None, bool, str]:
    """
    Define qué tipos de Google Places usar.
    - Categorías manuales del usuario → solo esas (prioridad).
    - Solo ia_auto → categorías IA ancladas al rubro/intenciones + mapeo interno.
    - Sin selección → None (flujo por rubro principal).
    """
    manual = _categorias_manuales(competidores_seleccionados)
    ia_auto = bool(competidores_seleccionados and "ia_auto" in competidores_seleccionados)

    if manual:
        return manual, ia_auto, "categorias_usuario"

    if ia_auto:
        sugeridos = [t for t in categorias_ia.get("competidores", []) if t]
        tipos: list[str] = []
        for t in sugeridos:
            if t not in tipos:
                tipos.append(t)
        if google_type and google_type not in tipos:
            tipos.insert(0, google_type)
        if not tipos:
            tipos = [google_type] if google_type else ["restaurant"]
        return tipos, True, "ia_rubro_intenciones"

    return None, False, "rubro_default"


def resolver_tipos_aliados_busqueda(
    aliados_seleccionados: list[str] | None,
    *,
    rubro: str,
    intenciones: str | None = None,
) -> tuple[list[str] | None, bool, str]:
    manual = _categorias_manuales(aliados_seleccionados)
    ia_auto = bool(aliados_seleccionados and "ia_auto" in aliados_seleccionados)

    if manual:
        return manual, ia_auto, "categorias_usuario"

    if ia_auto:
        from app.aliados_deterministico import resolver_aliados_por_rubro

        tipos = resolver_aliados_por_rubro(rubro, intenciones=intenciones)
        return tipos, True, "matriz_rubro"

    return None, False, "atractores_default"
