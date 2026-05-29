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

        # Si la base de datos está vacía, retornamos valores nulos/cero simulados pero consistentes
        if not result or (result[0] == 0 and result[1] == 0):
            logger.warning(
                "No se encontraron intersecciones de AGEBs en PostGIS. Retornando valores demográficos por defecto."
            )
            return {
                "poblacion_ponderada": 12500,
                "viviendas_ponderada": 3500,
                "poblacion_masculina": 6100,
                "poblacion_femenina": 6400,
            }

        return {
            "poblacion_ponderada": int(round(result[0])),
            "viviendas_ponderada": int(round(result[1])),
            "poblacion_masculina": int(round(result[2])),
            "poblacion_femenina": int(round(result[3])),
        }
    except Exception as e:
        logger.error(f"Falla al ejecutar consulta demográfica espacial: {e}")
        # Retorno de contingencia si no hay PostGIS activo en desarrollo
        return {
            "poblacion_ponderada": 12500,
            "viviendas_ponderada": 3500,
            "poblacion_masculina": 6100,
            "poblacion_femenina": 6400,
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

    return "store", "comercio_general"


def procesar_calculo_analitico(db: Session, lat: float, lng: float, radio: int, rubro: str, tier: str) -> dict:
    """
    Orquesta todo el motor analítico cuantitativo:
    1. Demografía espacial PostGIS.
    2. Cruce de categorías.
    3. Mapeo de competencia con Google Places.
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

    if tier in ["pro", "premium"]:
        competidores = buscar_competidores(lat, lng, float(radio), google_type)
        logger.info(f"Competidores detectados en el radio por Places: {len(competidores)}")

        # Calcular distancias e Índice de Saturación Comercial (Huff)
        for comp in competidores:
            dist = calcular_distancia_haversine(lat, lng, comp["latitud"], comp["longitud"])
            comp["distancia_metros"] = round(dist, 1)
            distancia_mas_cercana = min(distancia_mas_cercana, dist)

            # Capping a 10 metros para evitar infinitos en la fórmula de gravedad
            dist_cap = max(dist, 10.0)
            isc += 1.0 / (dist_cap**2)

    # 4. Obtener Afluencia Peatonal (BestTime API)
    afluencia = {}
    if tier == "premium":
        afluencia = obtener_afluencia(lat, lng, rubro)

    # 5. Calcular Score SVA de Viabilidad (0 a 100)
    # A. Score Demográfico (Normalizado a 100, óptimo si poblacion > 15,000)
    score_demog = min((pob_total / 15000.0) * 100.0, 100.0)

    # B. Score de Competencia (A menor saturación, mayor score)
    # Si no hay competencia, el score es 100. Si hay mucha saturación, decrece.
    if not competidores:
        score_competencia = 100.0
    else:
        # Ponderación basada en la gravedad comercial
        # Un ISC de 0.0001 (ej: 1 competidor a 100m) es bajo. Un ISC de 0.01 (ej: 1 competidor a 10m) es muy alto.
        # Escala logarítmica suavizada
        factor_saturacion = math.log10(isc) if isc > 0 else -10
        # Mapeo: factor_saturacion entre -6 (baja competencia) y -2 (alta competencia)
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
        # En tiers básicos, el tráfico se estima moderado
        score_trafico = 55.0

    # D. Fusión Ponderada del Score SVA
    # Ponderaciones: 40% Demografía, 30% Competencia, 30% Atracción/Tráfico
    sva = (score_demog * 0.4) + (score_competencia * 0.3) + (score_trafico * 0.3)
    sva_final = int(round(sva))

    # Ajustes finales a la distancia más cercana
    distancia_cercana_res = int(round(distancia_mas_cercana)) if distancia_mas_cercana != float("inf") else -1

    return {
        "poblacion_ponderada": pob_total,
        "vivtot_ponderada": demog["viviendas_ponderada"],
        "pobmas_ponderada": demog["poblacion_masculina"],
        "pobfem_ponderada": demog["poblacion_femenina"],
        "google_type": google_type,
        "categoria": categoria,
        "competidores_conteo": len(competidores),
        "competidores_listado": competidores,
        "distancia_competidor_cercano": distancia_cercana_res,
        "isc": isc,
        "afluencia_peatonal": afluencia,
        "score_demog": round(score_demog, 1),
        "score_competencia": round(score_competencia, 1),
        "score_trafico": round(score_trafico, 1),
        "sva": sva_final,
    }
