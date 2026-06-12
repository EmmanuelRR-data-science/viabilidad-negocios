"""Resolución de categorías y palabras clave para búsqueda de competidores/aliados."""

from __future__ import annotations


def contexto_giro_completo(rubro: str, intenciones: str | None = None) -> str:
    """Texto unificado para filtrar relevancia de giro (rubro + intenciones)."""
    r = (rubro or "").strip()
    i = (intenciones or "").strip()
    if r and i:
        return f"{r}. {i}"
    return r or i


def _categorias_manuales(seleccion: list[str] | None) -> list[str]:
    return [c for c in (seleccion or []) if c != "ia_auto"]


def keyword_places_para_ia(
    rubro: str,
    *,
    intenciones: str | None = None,
    competidores_adicionales: str | None = None,
    google_type: str = "store",
) -> str | None:
    """Palabra clave para afinar Nearby Search cuando el giro es libre o nicho."""
    if competidores_adicionales:
        primera = competidores_adicionales.split(",")[0].strip()
        if primera:
            return primera[:100]

    contexto = contexto_giro_completo(rubro, intenciones)
    if not contexto:
        return None

    if google_type in ("store", "establishment"):
        return contexto[:100]

    # Giro escrito en texto libre: afinar aunque el tipo Places sea más genérico.
    if len(contexto.split()) >= 2 or len(contexto) > 12:
        return contexto[:100]

    return None


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
    categorias_ia: dict,
) -> tuple[list[str] | None, bool, str]:
    manual = _categorias_manuales(aliados_seleccionados)
    ia_auto = bool(aliados_seleccionados and "ia_auto" in aliados_seleccionados)

    if manual:
        return manual, ia_auto, "categorias_usuario"

    if ia_auto:
        sugeridos = [t for t in categorias_ia.get("aliados", []) if t]
        if not sugeridos:
            sugeridos = ["transit_station", "school", "bank"]
        return sugeridos, True, "ia_rubro_intenciones"

    return None, False, "atractores_default"
