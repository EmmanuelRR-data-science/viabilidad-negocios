import logging
import math

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.besttime import obtener_afluencia
from app.google_places import buscar_competidores

logger = logging.getLogger("analytics")


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


def obtener_demografia_ponderada(db: Session, lat: float, lng: float, radio: int) -> dict:
    """
    Ejecuta una consulta geoespacial geodésica en PostgreSQL + PostGIS para calcular
    la población proporcional (ponderada por intersección) dentro del búfer de radio en metros.
    Usa NULLIF para evitar divisiones por cero de geometrías nulas.
    """
    logger.info(f"Ejecutando intersección proporcional en PostGIS para coordenadas ({lat}, {lng}) en radio {radio}m...")

    # Consulta SQL geoespacial optimizada con casteo geodésico
    query = text("""
        SELECT 
            COALESCE(SUM(pobtot * ST_Area(ST_Intersection(geom, ST_Buffer(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radio)::geometry)::geography) / NULLIF(ST_Area(geom::geography), 0)), 0) as pobtot,
            COALESCE(SUM(vivtot * ST_Area(ST_Intersection(geom, ST_Buffer(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radio)::geometry)::geography) / NULLIF(ST_Area(geom::geography), 0)), 0) as vivtot,
            COALESCE(SUM(pobmas * ST_Area(ST_Intersection(geom, ST_Buffer(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radio)::geometry)::geography) / NULLIF(ST_Area(geom::geography), 0)), 0) as pobmas,
            COALESCE(SUM(pobfem * ST_Area(ST_Intersection(geom, ST_Buffer(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radio)::geometry)::geography) / NULLIF(ST_Area(geom::geography), 0)), 0) as pobfem
        FROM agebs_demografia
        WHERE ST_Intersects(geom, ST_Buffer(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radio)::geometry);
    """)

    try:
        result = db.execute(query, {"lat": lat, "lng": lng, "radio": radio}).fetchone()

        # Si no hay intersección real con AGEBs (zona rural, lago, sin cartografía urbana)
        # devolvemos 0 honestamente — el reporte mostrará lo que realmente hay
        if not result or (result[0] == 0 and result[1] == 0):
            logger.warning(
                "No se encontraron intersecciones de AGEBs en PostGIS para las coordenadas dadas. "
                "Retornando 0 para reflejar la ausencia real de datos censales en la zona."
            )
            return {
                "poblacion_ponderada": 0,
                "viviendas_ponderada": 0,
                "poblacion_masculina": 0,
                "poblacion_femenina": 0,
            }

        return {
            "poblacion_ponderada": int(round(result[0])),
            "viviendas_ponderada": int(round(result[1])),
            "poblacion_masculina": int(round(result[2])),
            "poblacion_femenina": int(round(result[3])),
        }
    except Exception as e:
        logger.error(f"Falla al ejecutar consulta demográfica espacial: {e}")
        # En caso de error de conexión, devolvemos 0 — nunca valores inventados
        return {
            "poblacion_ponderada": 0,
            "viviendas_ponderada": 0,
            "poblacion_masculina": 0,
            "poblacion_femenina": 0,
        }


def resolver_google_type(db: Session, rubro: str) -> tuple[str, str]:
    """
    Busca en la tabla 'categorias_cruce' el mapeo del rubro ingresado al tipo de Google Places.
    """
    query = text("""
        SELECT google_place_type, categoria_negocio 
        FROM categorias_cruce 
        WHERE LOWER(nombre_scian) LIKE :rubro_like OR LOWER(categoria_negocio) LIKE :rubro_like
        LIMIT 1;
    """)
    try:
        rubro_like = f"%{rubro.lower().strip()}%"
        row = db.execute(query, {"rubro_like": rubro_like}).fetchone()
        if row:
            return row[0], row[1]
    except Exception as e:
        logger.error(f"Error al mapear categoría de rubro: {e}")

    # Fallbacks generales según palabras clave comunes
    rub_lower = rubro.lower()
    if "cafe" in rub_lower:
        return "cafe", "cafeteria"
    elif "farma" in rub_lower:
        return "pharmacy", "farmacia"
    elif "restauran" in rub_lower or "comida" in rub_lower:
        return "restaurant", "restaurante"
    elif "gym" in rub_lower or "gimnasio" in rub_lower:
        return "gym", "gimnasio"
    elif "veterinari" in rub_lower or "veterinary" in rub_lower:
        return "veterinary_care", "veterinaria"
    elif "mascota" in rub_lower or "perro" in rub_lower or "gato" in rub_lower or "pet" in rub_lower:
        return "pet_store", "accesorios_para_mascotas"
    elif "panaderia" in rub_lower or "pan" in rub_lower or "pasteler" in rub_lower:
        return "bakery", "panaderia"
    elif "ropa" in rub_lower or "boutique" in rub_lower or "vestido" in rub_lower:
        return "clothing_store", "tienda_de_ropa"
    elif "zapato" in rub_lower or "calzado" in rub_lower or "zapater" in rub_lower:
        return "shoe_store", "zapateria"
    elif "juguete" in rub_lower or "jugueter" in rub_lower:
        return "toy_store", "jugueteria"
    elif "dentista" in rub_lower or "dental" in rub_lower or "odontolog" in rub_lower:
        return "dentist", "dentista"
    elif "supermercado" in rub_lower or "super" in rub_lower:
        return "supermarket", "supermercado"

    return "store", "comercio_general"


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
) -> dict:
    """
    Orquesta todo el motor analítico cuantitativo:
    1. Demografía espacial PostGIS.
    2. Cruce de categorías.
    3. Mapeo de competencia con Google Places (estándar o personalizada).
    4. Curvas BestTime.
    5. Scoring normalizado SVA.
    """
    logger.info(f"Orquestando motor analítico cuantitativo en coordenadas ({lat}, {lng}) | Radio: {radio}m")

    # 1. Demografía proporcional
    demog = obtener_demografia_ponderada(db, lat, lng, radio)
    pob_total = demog["poblacion_ponderada"]

    # 2. Cruce de categorías
    google_type, categoria = resolver_google_type(db, rubro)
    logger.info(f"Mapeo de rubro '{rubro}' resuelto a: Google Type = '{google_type}' | Categoria = '{categoria}'")

    # 3. Buscar competidores (Google Places)
    competidores = []
    isc = 0.0
    distancia_mas_cercana = float("inf")

    bancos_conteo = 0
    escuelas_conteo = 0
    transporte_conteo = 0
    # Listas reales de aliados para el reporte — se consolidan en aliados_listado
    bancos_list: list = []
    escuelas_list: list = []
    transporte_list: list = []
    aliados_listado: list = []
    aliados_conteos: dict = {}

    competidores_sel_orig = competidores_seleccionados
    aliados_sel_orig = aliados_seleccionados

    ia_autodetect_competidores = False
    if competidores_seleccionados and "ia_auto" in competidores_seleccionados:
        ia_autodetect_competidores = True

    ia_autodetect_aliados = False
    if aliados_seleccionados and "ia_auto" in aliados_seleccionados:
        ia_autodetect_aliados = True

    if ia_autodetect_competidores or ia_autodetect_aliados:
        try:
            from app.bedrock import determinar_categorias_ia
            sugerencias = determinar_categorias_ia(rubro)
            logger.info(f"Categorías sugeridas por IA para '{rubro}': {sugerencias}")
            if ia_autodetect_competidores:
                competidores_seleccionados = sugerencias.get("competidores", ["restaurant"])
            if ia_autodetect_aliados:
                aliados_seleccionados = sugerencias.get("aliados", ["transit_station"])
        except Exception as ia_err:
            logger.error(f"Error al determinar categorías por IA: {ia_err}. Usando fallbacks estándar.")
            if ia_autodetect_competidores:
                competidores_seleccionados = None
            if ia_autodetect_aliados:
                aliados_seleccionados = None

    if tier in ["basico", "pro", "premium"]:
        if competidores_seleccionados:
            logger.info(f"Buscando competidores personalizados por Places: {competidores_seleccionados}...")
            seen_keys = set()
            for custom_type in competidores_seleccionados:
                found = buscar_competidores(lat, lng, float(radio), custom_type)
                for comp in found:
                    comp_key = (round(comp["latitud"], 5), round(comp["longitud"], 5))
                    if comp_key not in seen_keys:
                        seen_keys.add(comp_key)
                        comp["tipo"] = custom_type.replace("_", " ").title()
                        competidores.append(comp)
        else:
            # Si el tipo resuelto es genérico ("store") pero el usuario dio competidores_adicionales,
            # lo usamos como keyword de búsqueda en Google Places.
            keyword = None
            if google_type == "store" and competidores_adicionales:
                keyword = competidores_adicionales.strip()

            competidores = buscar_competidores(lat, lng, float(radio), google_type, keyword=keyword)
            for comp in competidores:
                comp["tipo"] = keyword.title() if keyword else categoria.replace("_", " ").title()
        logger.info(f"Competidores detectados en el radio por Places: {len(competidores)}")

        # Calcular distancias e Índice de Saturación Comercial (Huff)
        for comp in competidores:
            dist = calcular_distancia_haversine(lat, lng, comp["latitud"], comp["longitud"])
            comp["distancia_metros"] = round(dist, 1)
            distancia_mas_cercana = min(distancia_mas_cercana, dist)

            # Capping a 10 metros para evitar infinitos en la fórmula de gravedad
            dist_cap = max(dist, 10.0)
            isc += 1.0 / (dist_cap**2)

        # Ordenar competidores por distancia (de más cercano a más lejano)
        competidores.sort(key=lambda x: x.get("distancia_metros", 999999.0))

        if True:
            if aliados_seleccionados or aliados_adicionales:
                if aliados_seleccionados:
                    logger.info(f"Buscando aliados personalizados por Places: {aliados_seleccionados}...")
                    for custom_type in aliados_seleccionados:
                        try:
                            found_allies = buscar_competidores(lat, lng, float(radio), custom_type)
                            aliados_conteos[custom_type] = len(found_allies)
                            for ally in found_allies[:3]:
                                tipo_nombre = custom_type.replace("_", " ").title()
                                aliados_listado.append(
                                    {
                                        "nombre": ally.get("nombre", "Establecimiento sin nombre"),
                                        "tipo": tipo_nombre,
                                        "rating": ally.get("rating", 0.0),
                                        "user_ratings_total": ally.get("user_ratings_total", 0),
                                        "direccion": ally.get("direccion", ""),
                                        "latitud": ally.get("latitud"),
                                        "longitud": ally.get("longitud"),
                                    }
                                )
                        except Exception as ally_err:
                            logger.error(f"Falla al buscar aliado personalizado {custom_type}: {ally_err}")
                            aliados_conteos[custom_type] = 0

                if aliados_adicionales:
                    logger.info(f"Buscando aliados adicionales por palabra clave: {aliados_adicionales}...")
                    keywords = [kw.strip() for kw in aliados_adicionales.split(",") if kw.strip()]
                    for kw in keywords:
                        try:
                            # Buscamos con el wildcard "establishment" usando la palabra clave ingresada
                            found_allies = buscar_competidores(lat, lng, float(radio), "establishment", keyword=kw)
                            aliados_conteos[kw] = len(found_allies)
                            for ally in found_allies[:3]:
                                aliados_listado.append(
                                    {
                                        "nombre": ally.get("nombre", "Establecimiento sin nombre"),
                                        "tipo": kw.capitalize(),
                                        "rating": ally.get("rating", 0.0),
                                        "user_ratings_total": ally.get("user_ratings_total", 0),
                                        "direccion": ally.get("direccion", ""),
                                        "latitud": ally.get("latitud"),
                                        "longitud": ally.get("longitud"),
                                    }
                                )
                        except Exception as extra_ally_err:
                            logger.error(f"Falla al buscar aliado adicional '{kw}': {extra_ally_err}")
                            aliados_conteos[kw] = 0
            else:
                # Buscar atractores urbanos reales — si falla la API el conteo queda en 0, nunca inventado
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
                    "bank": bancos_conteo,
                    "school": escuelas_conteo,
                    "transit_station": transporte_conteo,
                }

                def _enriquecer_aliado(item: dict, tipo_semantico: str) -> dict:
                    return {
                        "nombre": item.get("nombre", "Establecimiento sin nombre"),
                        "tipo": tipo_semantico,
                        "rating": item.get("rating", 0.0),
                        "user_ratings_total": item.get("user_ratings_total", 0),
                        "direccion": item.get("direccion", ""),
                        "latitud": item.get("latitud"),
                        "longitud": item.get("longitud"),
                    }

                aliados_listado = (
                    [_enriquecer_aliado(b, "Institución Bancaria / Financiera") for b in bancos_list[:3]]
                    + [_enriquecer_aliado(e, "Centro Educativo") for e in escuelas_list[:3]]
                    + [_enriquecer_aliado(t, "Transporte Público") for t in transporte_list[:3]]
                )

    # 4. Obtener Afluencia Peatonal (BestTime API)
    afluencia = {}
    if True:
        afluencia = obtener_afluencia(lat, lng, rubro, competidores=competidores)

    # 5. Calcular Score SVA de Viabilidad (0 a 100)
    # A. Score Demográfico (Normalizado a 100, óptimo si poblacion > 15,000)
    score_demog = min((pob_total / 15000.0) * 100.0, 100.0)

    # B. Score de Competencia (A menor saturación, mayor score)
    if not competidores:
        score_competencia = 100.0
    else:
        factor_saturacion = math.log10(isc) if isc > 0 else -10
        if factor_saturacion <= -6:
            score_competencia = 100.0
        elif factor_saturacion >= -2:
            score_competencia = 10.0
        else:
            score_competencia = 100.0 - ((factor_saturacion - (-6)) / ((-2) - (-6)) * 90.0)

    # C. Score de Atracción de Tráfico (Basado en afluencia o POIs atractores)
    if tier == "premium" and afluencia.get("status") == "success":
        score_trafico = afluencia.get("saturación_promedio", 50.0)
    else:
        score_trafico = 55.0

    # D. Fusión Ponderada del Score SVA
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
        "competidores_listado": competidores,
        "distancia_competidor_cercano": distancia_cercana_res,
        "isc": isc,
        "afluencia_peatonal": afluencia,
        "score_demog": round(score_demog, 1),
        "score_competencia": round(score_competencia, 1),
        "score_trafico": round(score_trafico, 1),
        "sva": sva_final,
        "bancos_conteo": bancos_conteo,
        "escuelas_conteo": escuelas_conteo,
        "transporte_conteo": transporte_conteo,
        "aliados_listado": aliados_listado,
        "aliados_conteos": aliados_conteos,
        "competidores_seleccionados": competidores_sel_orig,
        "aliados_seleccionados": aliados_sel_orig,
        "competidores_ia_auto": ia_autodetect_competidores,
        "aliados_ia_auto": ia_autodetect_aliados,
    }
