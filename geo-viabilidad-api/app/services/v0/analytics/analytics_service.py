import logging
import math

from sqlalchemy.orm import Session

from app.clients.v0.besttime.besttime_client_processed import obtener_afluencia
from app.clients.v0.database import obtener_demografia_ponderada, resolver_google_type
from app.clients.v0.google.google_client_processed import (
    buscar_competidores,
    enriquecer_competidores_con_reseñas,
    enriquecer_lugares_con_vigencia,
)
from app.clients.v0.google.google_giro_filter import filtrar_competidores_por_giro
from app.core.config import DEV_MODE
from app.domain.competencia_busqueda import (
    contexto_giro_completo,
    keywords_busqueda_places,
    merge_competidores_por_clave,
    resolver_tipos_aliados_busqueda,
    resolver_tipos_competidores_busqueda,
    tipos_con_busqueda_proximidad,
)
from app.domain.demografia_segmentos import construir_segmentacion_desde_raw, segmentacion_vacia
from app.domain.nse import construir_nse_desde_raw, resolver_sin_censo
from app.domain.seleccion_atractores import seleccionar_atractores_destacados
from app.domain.vigencia_comercio import vigencia_sin_verificar
from app.services.tiers import get_tier_strategy

logger = logging.getLogger("analytics")

MIN_RESENAS_DESTACADO = 5
LIMITE_VIGENCIA_COMPETIDORES = 15
LIMITE_VIGENCIA_ALIADOS = 10


def calcular_nse(db: Session, lat: float, lng: float, radio: int, *, permitir_fallback_sin_censo: bool = False):
    """Orquesta I/O (DB client) + lógica pura (domain) para NSE."""
    from app.clients.v0.database import columnas_nse_disponibles, consultar_nse_censo

    if not columnas_nse_disponibles(db):
        return resolver_sin_censo(lat, lng, permitir_fallback_sin_censo=permitir_fallback_sin_censo)
    try:
        raw = consultar_nse_censo(db, lat, lng, radio)
    except Exception as err:
        logger.error("Error al consultar NSE en PostGIS: %s", err)
        return resolver_sin_censo(lat, lng, permitir_fallback_sin_censo=permitir_fallback_sin_censo)
    if not raw or raw["agebs_consultadas"] == 0:
        return resolver_sin_censo(lat, lng, permitir_fallback_sin_censo=permitir_fallback_sin_censo)
    escolaridad = raw["escolaridad_promedio"]
    internet = min(100.0, max(0.0, raw["internet_pct"]))
    autos = min(100.0, max(0.0, raw["autos_pct"]))
    if escolaridad <= 0 and internet <= 0 and autos <= 0:
        return resolver_sin_censo(lat, lng, permitir_fallback_sin_censo=permitir_fallback_sin_censo)
    return construir_nse_desde_raw(raw)


def calcular_segmentacion_demografica(db: Session, lat: float, lng: float, radio: int):
    """Orquesta I/O (DB client) + lógica pura (domain) para segmentación."""
    from geo_viabilidad_data.censo_segmentos_map import SEGMENTO_DB_COLUMNS

    from app.clients.v0.database import columnas_segmentos_disponibles, consultar_segmentacion

    if not columnas_segmentos_disponibles(db):
        return segmentacion_vacia()
    row = consultar_segmentacion(db, lat, lng, radio, list(SEGMENTO_DB_COLUMNS))
    if row is None:
        return segmentacion_vacia()
    return construir_segmentacion_desde_raw(row)


def buscar_competidores_unificado(
    lat: float,
    lng: float,
    radio: float,
    google_type: str,
    *,
    rubro: str,
    intenciones: str | None = None,
    competidores_adicionales: str | None = None,
) -> list:
    """Orquesta búsqueda HTTP via Google client + merge puro (domain)."""
    from app.clients.v0.google.google_client_processed import buscar_competidores as _buscar
    from app.clients.v0.google.google_client_processed import buscar_competidores_por_proximidad

    kws = keywords_busqueda_places(
        rubro,
        google_type=google_type,
        intenciones=intenciones,
        competidores_adicionales=competidores_adicionales,
    )
    lotes: list[list[dict]] = [_buscar(lat, lng, radio, google_type, keyword=kw) for kw in kws]
    if google_type in tipos_con_busqueda_proximidad():
        lotes.append(buscar_competidores_por_proximidad(lat, lng, google_type))
    return merge_competidores_por_clave(lotes)


def _activo_para_analisis(lugar: dict) -> bool:
    return bool(lugar.get("vigencia", {}).get("activo_para_analisis", True))


def _asegurar_vigencia_en_lugares(lugares: list[dict]) -> None:
    for lugar in lugares:
        if not lugar.get("vigencia"):
            lugar["vigencia"] = vigencia_sin_verificar()


def _calcular_isc_competidores(competidores: list[dict]) -> tuple[float, float]:
    """ISC y distancia mínima usando solo establecimientos activos según Google."""
    isc = 0.0
    distancia_mas_cercana = float("inf")
    for comp in competidores:
        if not _activo_para_analisis(comp):
            continue
        dist = comp.get("distancia_metros")
        if dist is None:
            continue
        distancia_mas_cercana = min(distancia_mas_cercana, float(dist))
        dist_cap = max(float(dist), 10.0)
        isc += 1.0 / (dist_cap**2)
    return isc, distancia_mas_cercana


def formatear_vigencia_corta(vigencia: dict | None) -> str:
    if not vigencia:
        return "Sin verificar"
    return str(vigencia.get("etiqueta") or "Sin verificar")


def calcular_distancia_haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calcula la distancia geodésica en metros entre dos puntos usando la fórmula de Haversine.
    """
    r = 6371000.0  # Radio de la Tierra en metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def formatear_distancia_metros(metros: float | int | None) -> str:
    """Formatea distancia geodésica en metros para UI y PDF."""
    if metros is None or metros < 0:
        return "—"
    m = float(metros)
    if m < 1000:
        return f"{m:.0f} m lineales"
    return f"{m / 1000:.2f} km lineales"


def asegurar_distancias_competidores(competidores: list[dict], lat: float, lng: float) -> None:
    """Completa distancia_metros en caché legacy cuando hay coordenadas del competidor."""
    for comp in competidores:
        if comp.get("distancia_metros") is not None:
            continue
        c_lat = comp.get("latitud")
        c_lng = comp.get("longitud")
        if c_lat is None or c_lng is None:
            continue
        comp["distancia_metros"] = round(calcular_distancia_haversine(lat, lng, c_lat, c_lng), 1)


def competidores_mejor_valorados(
    competidores: list[dict],
    *,
    top_n: int = 5,
    min_resenas: int = MIN_RESENAS_DESTACADO,
) -> list[dict]:
    """Top competidores por rating con volumen mínimo de reseñas en Google."""
    validos = [
        c
        for c in competidores
        if float(c.get("rating") or 0) > 0 and int(c.get("user_ratings_total") or 0) >= min_resenas
    ]
    validos.sort(
        key=lambda c: (
            -float(c.get("rating") or 0),
            -int(c.get("user_ratings_total") or 0),
            float(c.get("distancia_metros") or 999999.0),
        )
    )
    return validos[:top_n]


def competidores_mas_cercanos(competidores: list[dict], *, top_n: int = 8) -> list[dict]:
    """Top competidores por distancia al punto, sin filtrar por rating ni reseñas."""
    con_distancia = [c for c in competidores if c.get("distancia_metros") is not None]
    con_distancia.sort(key=lambda c: float(c.get("distancia_metros") or 999999.0))
    return con_distancia[:top_n]


def lectura_competidor_cercano(item: dict, *, min_resenas: int = MIN_RESENAS_DESTACADO) -> str:
    """Interpretacion determinista para rivales proximos (sin IA)."""
    rating = float(item.get("rating") or 0)
    resenas = int(item.get("user_ratings_total") or 0)

    if rating >= 4.5 and resenas >= min_resenas:
        return "Rival cercano y bien valorado en Google: friccion directa en calidad y ubicacion."
    if rating >= 3.0 and resenas >= min_resenas:
        return "Competidor aceptable muy proximo; diferenciate en servicio y propuesta."
    if rating > 0 and rating < 3.0:
        return (
            "Reputacion debil en Google; ocupa posicion cercana. Oportunidad de superar su "
            "propuesta, pero valida visibilidad y calidad para no repetir su patron."
        )
    if resenas < min_resenas:
        return (
            "Pocas reseñas en Google (muestra no representativa); presencia fisica cercana. "
            "Confirma en campo si compite por el mismo cliente."
        )
    return (
        "Sin calificacion publica en Google; presencia fisica cercana. Valida en campo "
        "si es competencia directa del giro."
    )


def resolver_competidores_destacados(
    competidores: list[dict],
    *,
    top_n: int = 5,
    min_resenas: int = MIN_RESENAS_DESTACADO,
) -> list[dict]:
    """Recalcula destacados con las reglas vigentes (ignora caché legacy)."""
    return competidores_mejor_valorados(competidores, top_n=top_n, min_resenas=min_resenas)


def resolver_competidores_destacados_para_reporte(
    competidores: list[dict],
    rubro: str,
    *,
    top_n: int = 5,
    min_resenas: int = MIN_RESENAS_DESTACADO,
    enriquecer_reseñas: bool = False,
) -> list[dict]:
    """
    Destacados con mínimo de reseñas y coherencia de giro (nombre/tipo/reseñas de Google).
    """
    candidatos = competidores_mejor_valorados(
        competidores,
        top_n=max(top_n * 3, top_n),
        min_resenas=min_resenas,
    )
    if enriquecer_reseñas and candidatos:
        try:
            enriquecer_competidores_con_reseñas(
                candidatos,
                min_resenas=min_resenas,
                max_reseñas_por_competidor=2,
            )
        except Exception as rev_err:
            logger.error("No se pudieron cargar reseñas para filtro de giro: %s", rev_err)
    contexto = contexto_giro_completo(rubro)
    relevantes = filtrar_competidores_por_giro(contexto, candidatos)
    return relevantes[:top_n]


def _enriquecer_aliado(item: dict, tipo_semantico: str) -> dict:
    return {
        "place_id": item.get("place_id"),
        "nombre": item.get("nombre", "Establecimiento sin nombre"),
        "tipo": tipo_semantico,
        "rating": item.get("rating", 0.0),
        "user_ratings_total": item.get("user_ratings_total", 0),
        "direccion": item.get("direccion", ""),
        "latitud": item.get("latitud"),
        "longitud": item.get("longitud"),
    }


from app.domain.sva_calculo import (
    calcular_score_competencia,
    calcular_score_demografico,
)


def _agregar_aliados_al_listado(
    found_allies: list,
    tipo_nombre: str,
    destino: list,
    seen_keys: set[tuple[float, float]],
) -> int:
    """Incluye todos los establecimientos detectados; el conteo coincide con mapa y PDF."""
    agregados = 0
    for ally in found_allies:
        lat = ally.get("latitud")
        lng = ally.get("longitud")
        if lat is None or lng is None:
            continue
        key = (round(lat, 5), round(lng, 5))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        destino.append(_enriquecer_aliado(ally, tipo_nombre))
        agregados += 1
    return agregados


def procesar_calculo_analitico(
    db: Session,
    lat: float,
    lng: float,
    radio: int,
    rubro: str,
    tier: str,
    competidores_seleccionados: list[str] | None = None,
    aliados_seleccionados: list[str] | None = None,
    competidores_adicionales: str | None = None,
    aliados_adicionales: str | None = None,
    intenciones: str | None = None,
    modo_analisis_aliados: str = "automatico",
    config_aliados_guiados: dict | None = None,
) -> dict:
    """
    Orquesta todo el motor analítico cuantitativo.
    """
    strategy = get_tier_strategy(tier)
    tier = strategy.tier_id
    if not strategy.uses_aliados_guiados():
        modo_analisis_aliados = "automatico"
        config_aliados_guiados = None

    logger.info(
        f"Orquestando motor analítico cuantitativo en coordenadas ({lat}, {lng}) | Radio: {radio}m | Tier: {tier}"
    )

    demog = obtener_demografia_ponderada(db, lat, lng, radio)
    pob_total = demog["poblacion_ponderada"]

    try:
        nse = calcular_nse(db, lat, lng, radio, permitir_fallback_sin_censo=DEV_MODE)
    except Exception as nse_err:
        logger.error("No se pudo calcular NSE: %s", nse_err)
        from app.domain.nse import construir_nse_fallback

        nse = construir_nse_fallback(lat, lng)

    try:
        segmentacion_demografica = calcular_segmentacion_demografica(db, lat, lng, radio)
    except Exception as seg_err:
        logger.error("No se pudo calcular segmentación demográfica: %s", seg_err)
        from app.domain.demografia_segmentos import _vacía

        segmentacion_demografica = _vacía()

    google_type, categoria = resolver_google_type(db, rubro)
    logger.info(f"Mapeo de rubro '{rubro}' resuelto a: Google Type = '{google_type}' | Categoria = '{categoria}'")

    competidores = []
    competidores_destacados: list[dict] = []
    competidores_activos = 0
    isc = 0.0
    distancia_mas_cercana = float("inf")

    bancos_conteo = 0
    escuelas_conteo = 0
    transporte_conteo = 0

    bancos_list: list = []
    escuelas_list: list = []
    transporte_list: list = []
    aliados_listado: list = []
    aliados_conteos: dict = {}
    aliados_seen_keys: set[tuple[float, float]] = set()

    competidores_sel_orig = competidores_seleccionados
    modo_aliados = (modo_analisis_aliados or "automatico").lower()
    config_guiada: dict = {}
    if modo_aliados == "guiado":
        from app.domain.aliados_guiados import validar_config_guiada

        config_guiada = validar_config_guiada(config_aliados_guiados, modo="guiado")
        aliados_sel_orig = list(config_guiada.get("atractores_confirmados") or [])
    else:
        aliados_sel_orig = aliados_seleccionados

    ia_autodetect_competidores = bool(competidores_seleccionados and "ia_auto" in competidores_seleccionados)
    ia_autodetect_aliados = bool(
        modo_aliados != "guiado" and aliados_seleccionados and "ia_auto" in aliados_seleccionados
    )

    categorias_ia: dict = {"competidores": [], "aliados": []}
    if ia_autodetect_competidores:
        try:
            from app.clients.v0.bedrock import determinar_categorias_ia

            categorias_ia = determinar_categorias_ia(
                rubro,
                intenciones=intenciones,
                google_type=google_type,
                categoria=categoria,
                competidores_adicionales=competidores_adicionales,
            )
            logger.info(
                "Categorías IA competidores para '%s': %s",
                rubro,
                categorias_ia.get("competidores"),
            )
        except Exception as ia_err:
            logger.error("Error al determinar categorías IA de competidores: %s", ia_err)

    tipos_competidores, ia_comp_activa, fuente_comp = resolver_tipos_competidores_busqueda(
        competidores_seleccionados,
        rubro=rubro,
        google_type=google_type,
        categorias_ia=categorias_ia,
    )
    tipos_aliados, ia_aliados_activa, fuente_aliados = resolver_tipos_aliados_busqueda(
        aliados_sel_orig if modo_aliados != "guiado" else None,
        rubro=rubro,
        intenciones=intenciones if modo_aliados != "guiado" else None,
        modo_analisis_aliados=modo_aliados,
        config_aliados_guiados=config_guiada if modo_aliados == "guiado" else None,
    )
    if ia_comp_activa:
        ia_autodetect_competidores = True
    if ia_aliados_activa:
        ia_autodetect_aliados = True

    contexto_giro = contexto_giro_completo(rubro, intenciones)

    if tier in ["basico", "pro", "premium"]:
        if tipos_competidores:
            logger.info(
                "Buscando competidores por Places (%s): %s",
                fuente_comp,
                tipos_competidores,
            )
            seen_keys = set()
            for custom_type in tipos_competidores:
                extra_kw = (
                    competidores_adicionales.split(",")[0].strip()
                    if custom_type in ("store", "establishment") and competidores_adicionales
                    else None
                )
                found = buscar_competidores_unificado(
                    lat,
                    lng,
                    float(radio),
                    custom_type,
                    rubro=rubro,
                    intenciones=intenciones,
                    competidores_adicionales=extra_kw,
                )
                for comp in found:
                    comp_key = (round(comp["latitud"], 5), round(comp["longitud"], 5))
                    if comp_key not in seen_keys:
                        seen_keys.add(comp_key)
                        comp["tipo"] = custom_type.replace("_", " ").title()
                        competidores.append(comp)
        else:
            competidores_raw = buscar_competidores_unificado(
                lat,
                lng,
                float(radio),
                google_type,
                rubro=rubro,
                intenciones=intenciones,
                competidores_adicionales=competidores_adicionales,
            )
            competidores = []
            for comp in competidores_raw:
                comp["tipo"] = categoria.replace("_", " ").title()
                competidores.append(comp)
        logger.info(f"Competidores detectados en el radio por Places: {len(competidores)}")

        if competidores:
            antes = len(competidores)
            competidores = filtrar_competidores_por_giro(rubro, competidores)
            logger.info(
                "Filtro de giro '%s': %s → %s competidores",
                rubro[:80],
                antes,
                len(competidores),
            )

        for comp in competidores:
            dist = calcular_distancia_haversine(lat, lng, comp["latitud"], comp["longitud"])
            comp["distancia_metros"] = round(dist, 1)

        competidores.sort(key=lambda x: x.get("distancia_metros", 999999.0))

        try:
            enriquecer_lugares_con_vigencia(
                competidores,
                limite=LIMITE_VIGENCIA_COMPETIDORES,
                max_reseñas=2,
            )
        except Exception as vig_err:
            logger.error("No se pudo enriquecer vigencia de competidores: %s", vig_err)
        _asegurar_vigencia_en_lugares(competidores)

        isc, distancia_mas_cercana = _calcular_isc_competidores(competidores)
        competidores_activos = sum(1 for c in competidores if _activo_para_analisis(c))

        enriquecer_reseñas = strategy.uses_bedrock()
        try:
            competidores_destacados = resolver_competidores_destacados_para_reporte(
                competidores,
                contexto_giro,
                top_n=5,
                enriquecer_reseñas=enriquecer_reseñas,
            )
        except Exception as dest_err:
            logger.error("No se pudieron resolver competidores destacados: %s", dest_err)
            competidores_destacados = resolver_competidores_destacados(competidores, top_n=5)

        if True:
            if tipos_aliados or aliados_adicionales:
                if tipos_aliados:
                    logger.info(
                        "Buscando aliados por Places (%s): %s",
                        fuente_aliados,
                        tipos_aliados,
                    )
                    for custom_type in tipos_aliados:
                        try:
                            found_allies = buscar_competidores(lat, lng, float(radio), custom_type)
                            tipo_nombre = custom_type.replace("_", " ").title()
                            aliados_conteos[custom_type] = _agregar_aliados_al_listado(
                                found_allies, tipo_nombre, aliados_listado, aliados_seen_keys
                            )
                        except Exception as ally_err:
                            logger.error(f"Falla al buscar aliado personalizado {custom_type}: {ally_err}")
                            aliados_conteos[custom_type] = 0

                if aliados_adicionales:
                    logger.info(f"Buscando aliados adicionales por palabra clave: {aliados_adicionales}...")
                    keywords = [kw.strip() for kw in aliados_adicionales.split(",") if kw.strip()]
                    for kw in keywords:
                        try:
                            found_allies = buscar_competidores(lat, lng, float(radio), "establishment", keyword=kw)
                            aliados_conteos[kw] = _agregar_aliados_al_listado(
                                found_allies, kw.capitalize(), aliados_listado, aliados_seen_keys
                            )
                        except Exception as extra_ally_err:
                            logger.error(f"Falla al buscar aliado adicional '{kw}': {extra_ally_err}")
                            aliados_conteos[kw] = 0
            else:
                try:
                    logger.info("Buscando bancos cercanos para la viabilidad de tráficos...")
                    bancos_list = buscar_competidores(lat, lng, float(radio), "bank")
                    bancos_conteo = len(bancos_list)
                except Exception as bank_err:
                    logger.error(f"Falla al buscar bancos en Places: {bank_err}. Conteo = 0.")
                    bancos_conteo = 0

                try:
                    logger.info("Buscando escuelas cercanas para la viabilidad de tráficos...")
                    escuelas_list = buscar_competidores(lat, lng, float(radio), "school")
                    escuelas_conteo = len(escuelas_list)
                except Exception as school_err:
                    logger.error(f"Falla al buscar escuelas en Places: {school_err}. Conteo = 0.")
                    escuelas_conteo = 0

                try:
                    logger.info("Buscando paradas de transporte público cercanas...")
                    transporte_list = buscar_competidores(lat, lng, float(radio), "transit_station")
                    transporte_conteo = len(transporte_list)
                except Exception as trans_err:
                    logger.error(f"Falla al buscar paradas de transporte: {trans_err}. Conteo = 0.")
                    transporte_conteo = 0

                aliados_conteos = {
                    "bank": _agregar_aliados_al_listado(
                        bancos_list, "Institución Bancaria / Financiera", aliados_listado, aliados_seen_keys
                    ),
                    "school": _agregar_aliados_al_listado(
                        escuelas_list, "Centro Educativo", aliados_listado, aliados_seen_keys
                    ),
                    "transit_station": _agregar_aliados_al_listado(
                        transporte_list, "Transporte Público", aliados_listado, aliados_seen_keys
                    ),
                }
                bancos_conteo = aliados_conteos["bank"]
                escuelas_conteo = aliados_conteos["school"]
                transporte_conteo = aliados_conteos["transit_station"]

    aliados_destacados: list[dict] = []
    atractores_seleccion: dict = {}
    if aliados_listado:
        for aliado in aliados_listado:
            if aliado.get("latitud") is not None and aliado.get("longitud") is not None:
                dist = calcular_distancia_haversine(lat, lng, aliado["latitud"], aliado["longitud"])
                aliado["distancia_metros"] = round(dist, 1)

        aliados_destacados, atractores_seleccion = seleccionar_atractores_destacados(aliados_listado, tier=tier)
        logger.info(
            "Atractores destacados: %s de %s detectados (%s)",
            len(aliados_destacados),
            len(aliados_listado),
            atractores_seleccion.get("regla", ""),
        )

        if aliados_destacados:
            try:
                enriquecer_lugares_con_vigencia(
                    aliados_destacados,
                    limite=LIMITE_VIGENCIA_ALIADOS,
                    max_reseñas=1,
                )
            except Exception as ally_vig_err:
                logger.error("No se pudo enriquecer vigencia de aliados destacados: %s", ally_vig_err)
            _asegurar_vigencia_en_lugares(aliados_destacados)

    afluencia = {}
    if True:
        afluencia = obtener_afluencia(lat, lng, rubro, competidores=competidores)

    score_demog, densidad_hab_km2 = calcular_score_demografico(pob_total, radio)
    score_competencia = calcular_score_competencia(isc)

    if strategy.tier_id == "premium" and afluencia.get("status") == "success":
        score_trafico = afluencia.get("saturación_promedio", 50.0)
    else:
        score_trafico = 55.0

    sva = (score_demog * 0.4) + (score_competencia * 0.3) + (score_trafico * 0.3)
    sva_final = int(round(sva))

    distancia_cercana_res = int(round(distancia_mas_cercana)) if distancia_mas_cercana != float("inf") else -1

    return {
        "poblacion_ponderada": pob_total,
        "vivtot_ponderada": demog["viviendas_ponderada"],
        "pobmas_ponderada": demog["poblacion_masculina"],
        "pobfem_ponderada": demog["poblacion_femenina"],
        "google_type": google_type,
        "categoria": categoria,
        "rubro": rubro,
        "competidores_conteo": len(competidores),
        "competidores_activos_conteo": competidores_activos if competidores else 0,
        "competidores_listado": competidores,
        "competidores_destacados": competidores_destacados,
        "distancia_competidor_cercano": distancia_cercana_res,
        "isc": isc,
        "afluencia_peatonal": afluencia,
        "densidad_hab_km2": densidad_hab_km2,
        "score_demog": score_demog,
        "score_competencia": round(score_competencia, 1),
        "score_trafico": round(score_trafico, 1),
        "sva": sva_final,
        "nse": nse,
        "segmentacion_demografica": segmentacion_demografica,
        "bancos_conteo": bancos_conteo,
        "escuelas_conteo": escuelas_conteo,
        "transporte_conteo": transporte_conteo,
        "aliados_listado": aliados_listado,
        "aliados_destacados": aliados_destacados,
        "atractores_seleccion": atractores_seleccion,
        "aliados_conteos": aliados_conteos,
        "competidores_seleccionados": competidores_sel_orig,
        "aliados_seleccionados": aliados_sel_orig,
        "competidores_ia_auto": ia_autodetect_competidores,
        "aliados_ia_auto": ia_autodetect_aliados,
        "aliados_fuente_busqueda": fuente_aliados,
        "modo_analisis_aliados": modo_aliados,
        "config_aliados_guiados": config_guiada if modo_aliados == "guiado" else None,
        "intenciones": intenciones,
    }


def obtener_resultado_reporte(
    orden_id: int,
    cognito_user_id: str,
    roles: list[str],
    db: Session,
) -> dict:
    import json

    from app.clients.v0.bedrock.bedrock_client_processed import generar_consideraciones_apertura
    from app.clients.v0.database import OrdenPago
    from app.clients.v0.google.google_client_processed import obtener_direccion
    from app.services.foda_service import foda_respaldo_cuantitativo as _foda_respaldo_cuantitativo
    from app.services.foda_service import generar_analisis_foda
    from app.services.v0.reports.reports_service import (
        AccesoNoAutorizadoError,
        OrdenNoEncontradaError,
        PagoNoAcreditadoError,
    )

    orden = db.query(OrdenPago).filter(OrdenPago.id == orden_id).first()
    if not orden:
        raise OrdenNoEncontradaError("La orden de análisis comercial solicitada no existe.")

    if orden.cognito_user_id != cognito_user_id and "admin" not in roles:
        raise AccesoNoAutorizadoError("No tienes autorización para acceder a este reporte comercial.")

    if orden.estado_pago != "approved":
        raise PagoNoAcreditadoError("El análisis está pendiente de pago.")

    strategy = get_tier_strategy(orden.tier_adquirido)
    if orden.tier_adquirido != strategy.tier_id:
        logger.warning(
            "Tier normalizado en resultado orden %s: %r -> %s",
            orden_id,
            orden.tier_adquirido,
            strategy.tier_id,
        )
        orden.tier_adquirido = strategy.tier_id

    if orden.resultado_json and orden.foda_json:
        logger.info(f"Cargando reporte de orden {orden_id} desde el caché de base de datos.")
        analisis_cuant = json.loads(orden.resultado_json)
        foda_inteligente = json.loads(orden.foda_json)
    else:
        logger.info(f"Reporte de orden {orden_id} no precalculado. Calculando en tiempo real...")
        direccion_res = obtener_direccion(float(orden.latitud), float(orden.longitud))

        competidores_sel = json.loads(orden.competidores_seleccionados) if orden.competidores_seleccionados else None
        aliados_sel = json.loads(orden.aliados_seleccionados) if orden.aliados_seleccionados else None
        config_guiada = json.loads(orden.config_aliados_guiados) if orden.config_aliados_guiados else None
        modo_aliados = getattr(orden, "modo_analisis_aliados", None) or "automatico"
        if strategy.uses_aliados_guiados() and modo_aliados == "guiado" and config_guiada:
            aliados_sel = config_guiada.get("atractores_confirmados")
        elif not strategy.uses_aliados_guiados():
            modo_aliados = "automatico"
            config_guiada = None
            aliados_sel = None

        analisis_cuant = procesar_calculo_analitico(
            db=db,
            lat=float(orden.latitud),
            lng=float(orden.longitud),
            radio=orden.radio_metros,
            rubro=orden.rubro,
            tier=strategy.tier_id,
            competidores_seleccionados=competidores_sel,
            aliados_seleccionados=aliados_sel,
            competidores_adicionales=orden.competidores_adicionales,
            aliados_adicionales=orden.aliados_adicionales,
            intenciones=orden.intenciones,
            modo_analisis_aliados=modo_aliados,
            config_aliados_guiados=config_guiada,
        )

        analisis_cuant["direccion"] = direccion_res["formato_completo"]
        analisis_cuant["competidores_adicionales"] = orden.competidores_adicionales
        analisis_cuant["aliados_adicionales"] = orden.aliados_adicionales
        analisis_cuant["radio_metros"] = orden.radio_metros
        analisis_cuant["tier_adquirido"] = strategy.tier_id

        if strategy.uses_bedrock():
            try:
                foda_inteligente = generar_analisis_foda(analisis_cuant, orden.intenciones)
            except Exception as foda_err:
                logger.error("FODA no disponible para orden %s: %s. Usando respaldo.", orden_id, foda_err)
                foda_inteligente = _foda_respaldo_cuantitativo(
                    analisis_cuant,
                    orden.rubro,
                    comp_adicionales=orden.competidores_adicionales,
                    aliados_adicionales=orden.aliados_adicionales,
                )
        else:
            foda_inteligente = _foda_respaldo_cuantitativo(
                analisis_cuant,
                orden.rubro,
                comp_adicionales=orden.competidores_adicionales,
                aliados_adicionales=orden.aliados_adicionales,
            )

        foda_cache = {k: v for k, v in foda_inteligente.items() if k == "_fuente" or not str(k).startswith("_")}
        orden.resultado_json = json.dumps(analisis_cuant, default=str)
        orden.foda_json = json.dumps(foda_cache, default=str)
        db.commit()

    if not foda_inteligente.get("consideraciones_apertura"):
        foda_inteligente["consideraciones_apertura"] = generar_consideraciones_apertura(analisis_cuant)

    lista_comp = analisis_cuant.get("competidores_listado") or []
    asegurar_distancias_competidores(lista_comp, float(orden.latitud), float(orden.longitud))
    enriquecer_reseñas = strategy.uses_bedrock()
    analisis_cuant["competidores_destacados"] = resolver_competidores_destacados_para_reporte(
        lista_comp,
        orden.rubro,
        top_n=5,
        enriquecer_reseñas=enriquecer_reseñas,
    )

    return {
        "status": "success",
        "orden": {
            "id": orden.id,
            "checkout_id": orden.checkout_id,
            "tier": strategy.tier_id,
            "monto": float(orden.monto),
            "fecha_aprobacion": orden.fecha_aprobacion,
            "competidores_adicionales": orden.competidores_adicionales,
            "aliados_adicionales": orden.aliados_adicionales,
            "pdf_listo": bool(orden.s3_key_reporte),
        },
        "metricas": analisis_cuant,
        "analisis_estrategico_ia": {k: v for k, v in foda_inteligente.items() if not str(k).startswith("_")},
    }


# ---------------------------------------------------------------------------
# Funciones delegadas por el router (thin-router pattern)
# ---------------------------------------------------------------------------


def sugerir_aliados_service(body) -> dict:
    """Delegación del endpoint de sugerencia de aliados guiados."""
    from app.domain.aliados_guiados import sugerir_atractores
    from app.exceptions import ValidationUserError

    try:
        sugerencias = sugerir_atractores(
            body.rubro,
            perfil_cliente=body.perfil_cliente,
            horarios_pico=body.horarios_pico,
        )
        return {"status": "success", "sugerencias": sugerencias}
    except Exception as exc:
        logger.error("Falla al sugerir aliados: %s", exc)
        raise ValidationUserError(str(exc)) from exc


def geocodificar_service(lat: float, lng: float) -> dict:
    """Geocodificación inversa delegada al Google client."""
    from app.clients.v0.google.google_client_processed import obtener_direccion

    logger.info("Petición de geocodificación para (%s, %s)", lat, lng)
    direccion_res = obtener_direccion(lat, lng)
    return {"status": "success", "coordenadas": {"lat": lat, "lng": lng}, "direccion": direccion_res}


def buscar_direccion_service(direccion_query: str) -> dict:
    """Geocodificación directa por texto."""
    from app.clients.v0.google.google_client_processed import buscar_coordenadas_por_direccion
    from app.exceptions import ExternalDependencyError

    try:
        resultados = buscar_coordenadas_por_direccion(direccion_query)
        return {"status": "success", "resultados": resultados}
    except Exception as e:
        logger.error("Falla al geocodificar dirección '%s': %s", direccion_query, e)
        raise ExternalDependencyError(
            "Falla de comunicación con el servicio de geocodificación de Google.",
            suggested_action="Por favor, intenta de nuevo en unos segundos.",
        ) from e


def obtener_vista_previa_service(
    db: Session,
    lat: float,
    lng: float,
    radio_metros: int,
    rubro: str,
    *,
    competidores_sel=None,
    aliados_sel=None,
    intenciones=None,
    competidores_adicionales=None,
    aliados_adicionales=None,
    modo_aliados: str = "automatico",
    config_guiada=None,
) -> dict:
    """Ensamble completo de la vista previa gratuita — el router solo invoca esto."""
    from app.clients.v0.google.google_client_processed import obtener_direccion

    resultado = procesar_calculo_analitico(
        db,
        lat,
        lng,
        radio_metros,
        rubro,
        tier="premium",
        competidores_seleccionados=competidores_sel,
        aliados_seleccionados=aliados_sel,
        intenciones=intenciones,
        competidores_adicionales=competidores_adicionales,
        aliados_adicionales=aliados_adicionales,
        modo_analisis_aliados=modo_aliados,
        config_aliados_guiados=config_guiada,
    )
    return {
        "status": "success",
        "coordenadas": {"lat": lat, "lng": lng},
        "radio_metros": radio_metros,
        "rubro": rubro,
        "tier": "gratuito",
        "poblacion_estimada": resultado["poblacion_ponderada"],
        "competidores_conteo": resultado["competidores_conteo"],
        "score_viabilidad_sva": resultado["sva"],
        "score_demog": resultado["score_demog"],
        "score_competencia": resultado["score_competencia"],
        "score_trafico": resultado["score_trafico"],
        "densidad_hab_km2": resultado["densidad_hab_km2"],
        "direccion": obtener_direccion(lat, lng)["formato_completo"],
        "competidores_listado": resultado["competidores_listado"],
        "competidores_destacados": resultado["competidores_destacados"],
        "aliados_listado": resultado["aliados_listado"],
        "aliados_destacados": resultado.get("aliados_destacados", []),
        "atractores_seleccion": resultado.get("atractores_seleccion", {}),
        "aliados_conteos": resultado["aliados_conteos"],
        "afluencia_peatonal": resultado["afluencia_peatonal"],
        "mensaje_tier": (
            "¡Estás viendo la vista previa gratuita! "
            "Compra el reporte Básico o Pro para desbloquear mapas detallados "
            "de competencia, o Premium para afluencia y diagnóstico estratégico inteligente con IA."
        ),
    }
