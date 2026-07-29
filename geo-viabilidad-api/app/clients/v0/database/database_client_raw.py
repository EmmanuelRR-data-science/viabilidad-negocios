"""Cliente Raw de PostgreSQL/PostGIS: conexión, sesión y queries SQL."""

from __future__ import annotations

import logging

from geo_viabilidad_data.database import Base, SessionLocal, engine, get_db
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("database_client_raw")

__all__ = ["Base", "SessionLocal", "engine", "get_db"]

# ---------------------------------------------------------------------------
# Constantes SQL espaciales reutilizables
# ---------------------------------------------------------------------------
_BUFFER_GEOM = "ST_Buffer(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radio)::geometry"
_PESO_INTERSECCION = (
    "ST_Area(ST_Intersection(geom, " + _BUFFER_GEOM + ")::geography) / NULLIF(ST_Area(geom::geography), 0)"
)


# ---------------------------------------------------------------------------
# Demografia ponderada (PostGIS)
# ---------------------------------------------------------------------------
def query_demografia_ponderada(db: Session, lat: float, lng: float, radio: int) -> dict | None:
    """Ejecuta intersección proporcional en PostGIS para población en el buffer."""
    query = text(f"""
        SELECT
            COALESCE(SUM(pobtot * {_PESO_INTERSECCION}), 0) as pobtot,
            COALESCE(SUM(vivtot * {_PESO_INTERSECCION}), 0) as vivtot,
            COALESCE(SUM(pobmas * {_PESO_INTERSECCION}), 0) as pobmas,
            COALESCE(SUM(pobfem * {_PESO_INTERSECCION}), 0) as pobfem
        FROM agebs_demografia
        WHERE ST_Intersects(geom, {_BUFFER_GEOM});
    """)
    try:
        result = db.execute(query, {"lat": lat, "lng": lng, "radio": radio}).fetchone()
        if not result or (result[0] == 0 and result[1] == 0):
            return None
        return {
            "pobtot": float(result[0]),
            "vivtot": float(result[1]),
            "pobmas": float(result[2]),
            "pobfem": float(result[3]),
        }
    except Exception as e:
        logger.error("Falla al ejecutar consulta demográfica espacial: %s", e)
        return None


# ---------------------------------------------------------------------------
# Resolución de categoría Google Type desde la tabla categorias_cruce
# ---------------------------------------------------------------------------
def query_google_type(db: Session, rubro: str) -> tuple[str, str] | None:
    """Busca en categorias_cruce el mapeo rubro → google_place_type."""
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
            return str(row[0]), str(row[1])
    except Exception as e:
        logger.error("Error al mapear categoría de rubro: %s", e)
    return None


# ---------------------------------------------------------------------------
# NSE — verificación de columnas y consulta censo
# ---------------------------------------------------------------------------
def query_columnas_nse_disponibles(db: Session) -> bool:
    try:
        row = db.execute(
            text("""
                SELECT COUNT(*) AS total
                FROM information_schema.columns
                WHERE table_name = 'agebs_demografia'
                  AND column_name IN ('graproes', 'vph_autom', 'vph_inter', 'vph_pc')
            """)
        ).fetchone()
        return bool(row and row[0] >= 4)
    except Exception as err:
        logger.warning("No se pudo verificar columnas NSE: %s", err)
        return False


def query_nse_censo(db: Session, lat: float, lng: float, radio: int) -> dict | None:
    query = text(f"""
        WITH intersectados AS (
            SELECT
                pobtot,
                vivtot,
                graproes,
                vph_autom,
                vph_inter,
                vph_pc,
                {_PESO_INTERSECCION} AS peso
            FROM agebs_demografia
            WHERE ST_Intersects(geom, {_BUFFER_GEOM})
              AND pobtot > 0
        )
        SELECT
            COALESCE(
                SUM(pobtot * peso * NULLIF(graproes, -1))
                / NULLIF(SUM(CASE WHEN graproes IS NOT NULL AND graproes >= 0 THEN pobtot * peso ELSE 0 END), 0),
                0
            ) AS escolaridad_promedio,
            COALESCE(SUM(vph_inter * peso) / NULLIF(SUM(vivtot * peso), 0) * 100, 0) AS internet_pct,
            COALESCE(SUM(vph_autom * peso) / NULLIF(SUM(vivtot * peso), 0) * 100, 0) AS autos_pct,
            COALESCE(SUM(vph_pc * peso) / NULLIF(SUM(vivtot * peso), 0) * 100, 0) AS pc_pct,
            COUNT(*) AS agebs_consultadas
        FROM intersectados
    """)
    row = db.execute(query, {"lat": lat, "lng": lng, "radio": radio}).fetchone()
    if not row:
        return None
    return {
        "escolaridad_promedio": float(row[0] or 0),
        "internet_pct": float(row[1] or 0),
        "autos_pct": float(row[2] or 0),
        "pc_pct": float(row[3] or 0),
        "agebs_consultadas": int(row[4] or 0),
    }


# ---------------------------------------------------------------------------
# Segmentación demográfica
# ---------------------------------------------------------------------------
def query_columnas_segmentos_disponibles(db: Session) -> bool:
    try:
        row = db.execute(
            text("""
                SELECT COUNT(*) AS total
                FROM information_schema.columns
                WHERE table_name = 'agebs_demografia'
                  AND column_name = 'pob0_14'
            """)
        ).fetchone()
        return bool(row and row[0] >= 1)
    except Exception as err:
        logger.warning("No se pudo verificar columnas de segmentación: %s", err)
        return False


def query_segmentacion_demografica(db: Session, lat: float, lng: float, radio: int, columnas: list[str]) -> dict | None:
    """Ejecuta la query de segmentación demográfica ponderada."""
    weighted_cols = ",\n            ".join(
        f"COALESCE(SUM({col} * {_PESO_INTERSECCION}), 0) AS {col}" for col in columnas
    )
    query = text(f"""
        SELECT
            COUNT(*) AS agebs_consultadas,
            {weighted_cols}
        FROM agebs_demografia
        WHERE ST_Intersects(geom, {_BUFFER_GEOM})
          AND pobtot > 0
    """)
    try:
        row = db.execute(query, {"lat": lat, "lng": lng, "radio": radio}).mappings().first()
    except Exception as err:
        logger.error("Error consultando segmentación demográfica: %s", err)
        return None
    if not row or int(row["agebs_consultadas"] or 0) == 0:
        return None
    return dict(row)


# ---------------------------------------------------------------------------
# Lectura de OrdenPago por id
# ---------------------------------------------------------------------------
def query_orden_por_id(db: Session, orden_id: int):
    """Retorna la OrdenPago o None."""
    from geo_viabilidad_data.models import OrdenPago

    return db.query(OrdenPago).filter(OrdenPago.id == orden_id).first()
