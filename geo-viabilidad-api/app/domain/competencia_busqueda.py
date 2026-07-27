"""Resolución de categorías y palabras clave para búsqueda de competidores/aliados."""

from __future__ import annotations

import unicodedata

# Texto placeholder del checkout cuando el usuario deja intenciones vacías — no sirve como keyword.
_INTENCIONES_PLACEHOLDER = (
    "evaluación comercial del giro en la zona residencial mexicana",
    "evaluacion comercial del giro en la zona residencial mexicana",
)

# Rubro interno → keywords canónicos para Nearby Search (nunca slugs técnicos).
_RUBRO_KEYWORDS_CANONICOS: dict[str, list[str]] = {
    "restaurante_carta": ["restaurante"],
    "restaurante": ["restaurante"],
    "comida_rapida": ["comida rapida", "restaurante"],
    "fast_food": ["comida rapida", "restaurante"],
    "panaderia": ["panaderia", "pasteleria"],
    "bakery": ["panaderia", "pasteleria"],
    "cafeteria": ["cafeteria", "cafe"],
    "cafe": ["cafeteria", "cafe"],
    "floreria": ["floreria", "flores"],
    "farmacia": ["farmacia"],
    "gimnasio": ["gimnasio", "gym"],
}

_TIPOS_CON_BUSQUEDA_PROXIMIDAD = frozenset(
    {"restaurant", "meal_takeaway", "meal_delivery", "cafe", "bakery", "food", "bar"}
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


def _normalizar_clave_rubro(rubro: str) -> str:
    limpio = unicodedata.normalize("NFKD", str(rubro or ""))
    limpio = "".join(ch for ch in limpio if not unicodedata.combining(ch))
    limpio = limpio.lower().strip().replace(" ", "_")
    return limpio


def _dedupe_keywords(keywords: list[str | None]) -> list[str | None]:
    vistos: set[str | None] = set()
    resultado: list[str | None] = []
    for kw in keywords:
        clave = kw.lower() if isinstance(kw, str) else None
        if clave in vistos:
            continue
        vistos.add(clave)
        resultado.append(kw)
    return resultado


def keywords_busqueda_places(
    rubro: str,
    *,
    google_type: str = "store",
    intenciones: str | None = None,
    competidores_adicionales: str | None = None,
) -> list[str | None]:
    """
    Lista ordenada de keywords para unir búsquedas Places.
    Siempre incluye None (sin keyword) como primera estrategia.
    """
    if competidores_adicionales:
        primera = competidores_adicionales.split(",")[0].strip()
        if primera:
            return _dedupe_keywords([None, primera[:80]])

    clave = _normalizar_clave_rubro(rubro)
    canon = list(_RUBRO_KEYWORDS_CANONICOS.get(clave, []))

    humano = (rubro or "").replace("_", " ").strip()
    extra = _intenciones_utiles_para_keyword(intenciones)

    if not canon and google_type == "restaurant":
        canon = ["restaurante"]

    keywords: list[str | None] = [None]

    if extra and humano:
        humano_norm = humano.lower()
        extra_norm = extra.lower()
        if extra_norm.startswith(humano_norm):
            extra = extra[len(humano) :].lstrip(" .,;:-")
        if extra and extra.lower() not in humano_norm:
            keywords.append(f"{humano} {extra}"[:100])
    elif clave not in _RUBRO_KEYWORDS_CANONICOS and humano and _normalizar_clave_rubro(humano) == clave:
        keywords.append(humano[:80])
    elif not canon and humano and google_type in ("store", "establishment"):
        keywords.append(humano[:80])
    elif not canon and humano and len(humano) <= 40:
        keywords.append(humano[:80])

    keywords.extend(canon)
    return _dedupe_keywords(keywords)


def keyword_places_para_ia(
    rubro: str,
    *,
    intenciones: str | None = None,
    competidores_adicionales: str | None = None,
    google_type: str = "store",
) -> str | None:
    """Palabra clave principal (legible) para logs/UI; no usar como única búsqueda."""
    if competidores_adicionales:
        primera = competidores_adicionales.split(",")[0].strip()
        if primera:
            return primera[:80]

    clave = _normalizar_clave_rubro(rubro)
    humano = (rubro or "").strip()
    extra = _intenciones_utiles_para_keyword(intenciones)

    if extra and humano:
        humano_norm = humano.lower()
        extra_norm = extra.lower()
        if extra_norm.startswith(humano_norm):
            resto = extra[len(humano) :].lstrip(" .,;:-")
            return f"{humano} {resto}"[:100] if resto else humano[:80]
        if extra_norm not in humano_norm.replace("_", " "):
            return f"{humano} {extra}"[:100]

    if clave in _RUBRO_KEYWORDS_CANONICOS:
        if humano and "_" not in humano and _normalizar_clave_rubro(humano) == clave:
            return humano[:80]
        return _RUBRO_KEYWORDS_CANONICOS[clave][0]

    for kw in keywords_busqueda_places(
        rubro,
        google_type=google_type,
        intenciones=intenciones,
        competidores_adicionales=competidores_adicionales,
    ):
        if kw:
            return kw
    display = humano.replace("_", " ").strip()
    return display[:80] if display else None


def _clave_competidor(comp: dict) -> tuple:
    return (round(float(comp["latitud"]), 5), round(float(comp["longitud"]), 5))


def merge_competidores_por_clave(
    lotes: list[list[dict]],
) -> list[dict]:
    """Merge puro de lotes de competidores por coordenada-clave (sin I/O)."""
    merged: dict[tuple, dict] = {}
    for batch in lotes:
        for comp in batch:
            merged.setdefault(_clave_competidor(comp), comp)
    return list(merged.values())


def tipos_con_busqueda_proximidad() -> frozenset[str]:
    """Expone los tipos de Google Places que requieren búsqueda por proximidad."""
    return _TIPOS_CON_BUSQUEDA_PROXIMIDAD


def buscar_competidores_ia_con_reintento(
    lat: float,
    lng: float,
    radio: float,
    google_type: str,
    *,
    rubro: str,
    keyword: str | None,
) -> list:
    """Compatibilidad: delega en el servicio (no en domain)."""
    raise NotImplementedError(
        "buscar_competidores_ia_con_reintento ya no está en domain. "
        "Usa analytics_service.buscar_competidores_unificado."
    )


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
    modo_analisis_aliados: str = "automatico",
    config_aliados_guiados: dict | None = None,
) -> tuple[list[str] | None, bool, str]:
    if (modo_analisis_aliados or "automatico").lower() == "guiado":
        from app.domain.aliados_guiados import validar_config_guiada

        config = validar_config_guiada(config_aliados_guiados, modo="guiado")
        tipos = list(config.get("atractores_confirmados") or [])
        return tipos, False, "guiado_usuario"

    manual = _categorias_manuales(aliados_seleccionados)
    ia_auto = bool(aliados_seleccionados and "ia_auto" in aliados_seleccionados)

    if manual:
        return manual, ia_auto, "categorias_usuario"

    if ia_auto:
        from app.domain.aliados_deterministico import resolver_aliados_por_rubro

        tipos = resolver_aliados_por_rubro(rubro, intenciones=intenciones)
        return tipos, True, "matriz_rubro"

    return None, False, "atractores_default"
