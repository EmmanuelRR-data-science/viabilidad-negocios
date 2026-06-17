"""Segmentación demográfica ponderada por radio (Censo INEGI 2020 + PostGIS)."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.censo_segmentos_map import PIRAMIDE_GRUPOS, SEGMENTO_DB_COLUMNS
from app.schemas_demografia import PiramideGrupo, SegmentacionDemografica

logger = logging.getLogger("demografia_segmentos")

_BUFFER_GEOM = (
    "ST_Buffer(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radio)::geometry"
)
_PESO = (
    "ST_Area(ST_Intersection(geom, "
    + _BUFFER_GEOM
    + ")::geography) / NULLIF(ST_Area(geom::geography), 0)"
)


def _columnas_segmentos_disponibles(db: Session) -> bool:
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


def _vacía() -> SegmentacionDemografica:
    return {
        "fuente": "sin_datos",
        "agebs_consultadas": 0,
        "pob0_14": 0,
        "pob15_64": 0,
        "pob65_mas": 0,
        "piramide": [],
        "pea": 0,
        "pocupada": 0,
        "pdesocup": 0,
        "pe_inac": 0,
        "p15a17a": 0,
        "p18a24a": 0,
        "p8a14an": 0,
    }


def calcular_segmentacion_demografica(
    db: Session, lat: float, lng: float, radio: int
) -> SegmentacionDemografica:
    if not _columnas_segmentos_disponibles(db):
        return _vacía()

    weighted_cols = ",\n            ".join(
        f"COALESCE(SUM({col} * {_PESO}), 0) AS {col}" for col in SEGMENTO_DB_COLUMNS
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
        return _vacía()

    if not row or int(row["agebs_consultadas"] or 0) == 0:
        return _vacía()

    raw = {col: int(round(float(row[col] or 0))) for col in SEGMENTO_DB_COLUMNS}
    if raw.get("pob0_14", 0) <= 0 and raw.get("p_0a2_f", 0) <= 0:
        return _vacía()

    piramide: list[PiramideGrupo] = []
    for etiqueta, col_f, col_m in PIRAMIDE_GRUPOS:
        piramide.append(
            {
                "etiqueta": etiqueta,
                "mujeres": raw.get(col_f, 0),
                "hombres": raw.get(col_m, 0),
            }
        )

    return {
        "fuente": "censo_2020",
        "agebs_consultadas": int(row["agebs_consultadas"]),
        "pob0_14": raw.get("pob0_14", 0),
        "pob15_64": raw.get("pob15_64", 0),
        "pob65_mas": raw.get("pob65_mas", 0),
        "piramide": piramide,
        "pea": raw.get("pea", 0),
        "pocupada": raw.get("pocupada", 0),
        "pdesocup": raw.get("pdesocup", 0),
        "pe_inac": raw.get("pe_inac", 0),
        "p15a17a": raw.get("p15a17a", 0),
        "p18a24a": raw.get("p18a24a", 0),
        "p8a14an": raw.get("p8a14an", 0),
    }


def pct_segmento(valor: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((valor / total) * 100, 1)


def segmentos_destacados_por_rubro(rubro: str, seg: SegmentacionDemografica, pob_total: int) -> list[tuple[str, int, float, str]]:
    """Retorna hasta 3 segmentos censales relevantes al rubro (hab, %, nota)."""
    rubro_l = (rubro or "").lower()
    candidatos: list[tuple[str, int, str]] = []

    def add(etiqueta: str, valor: int, nota: str):
        if valor > 0:
            candidatos.append((etiqueta, valor, nota))

    jovenes = sum(g["mujeres"] + g["hombres"] for g in seg["piramide"] if g["etiqueta"] in ("18-24 años", "15-17 años"))
    adultos_mayores = sum(g["mujeres"] + g["hombres"] for g in seg["piramide"] if g["etiqueta"] == "60+ años")
    ninos = seg["pob0_14"]

    if "cafe" in rubro_l or "cafeter" in rubro_l:
        add("Jóvenes y adultos 15-24 años", jovenes, "Horario laboral y consumo diario")
        add("Población económicamente activa", seg["pea"], "Trabajadores y oficinistas en el radio")
        add("Población 25-59 años", seg["pob15_64"] - jovenes, "Poder adquisitivo estable")
    elif "farma" in rubro_l:
        add("Población 0-14 años", ninos, "Familias con demanda pediátrica")
        add("Adultos mayores (60+)", adultos_mayores, "Medicamentos crónicos y consulta")
        add("Población 25-59 años", max(0, seg["pob15_64"] - jovenes), "Cuidado personal recurrente")
    elif "gym" in rubro_l or "gimnasio" in rubro_l:
        add("Jóvenes 15-24 años", jovenes, "Fitness y entrenamiento")
        add("Estudiantes 15-24 (asisten escuela)", seg["p15a17a"] + seg["p18a24a"], "Horarios flexibles")
        add("Población ocupada", seg["pocupada"], "Rutina post-jornada laboral")
    else:
        add("Población en edad laboral (15-64)", seg["pob15_64"], "Demanda comercial principal")
        add("Población económicamente activa", seg["pea"], "Flujo de consumo cotidiano")
        add("Población 0-14 años", ninos, "Familias residentes")

    candidatos.sort(key=lambda x: x[1], reverse=True)
    return [(e, v, pct_segmento(v, pob_total), n) for e, v, n in candidatos[:3]]
