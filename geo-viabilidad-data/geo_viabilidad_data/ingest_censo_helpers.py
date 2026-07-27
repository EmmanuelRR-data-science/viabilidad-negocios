"""Utilidades compartidas para ingesta censal INEGI 2020 por AGEB."""

from __future__ import annotations

import pandas as pd

from geo_viabilidad_data.censo_segmentos_map import SEGMENTO_CENSO_MAP, SEGMENTO_DB_COLUMNS
from geo_viabilidad_data.ingest_shapefile_utils import normalize_cvegeo

NSE_CENSO_COLUMNS = ("GRAPROES", "VIVPAR_HAB", "VPH_AUTOM", "VPH_INTER", "VPH_PC")

REQUIRED_CENSO_COLUMNS = ("ENTIDAD", "MUN", "LOC", "AGEB", "MZA", "POBTOT", "POBFEM", "POBMAS", "VIVTOT")

_BASE_INSERT_COLS = (
    "cve_ageb",
    "entidad",
    "municipio",
    "geom",
    "pobtot",
    "pobmas",
    "pobfem",
    "vivtot",
    "graproes",
    "vivpar_hab",
    "vph_autom",
    "vph_inter",
    "vph_pc",
)
_ALL_INSERT_COLS = _BASE_INSERT_COLS + SEGMENTO_DB_COLUMNS

_INSERT_COLS_SQL = ", ".join(_ALL_INSERT_COLS)
_INSERT_PARAMS_SQL = ", ".join(
    [
        ":cve_ageb",
        ":entidad",
        ":municipio",
        "CASE WHEN :wkt IS NOT NULL THEN ST_GeomFromText(:wkt, 4326) ELSE NULL END",
        ":pobtot",
        ":pobmas",
        ":pobfem",
        ":vivtot",
        ":graproes",
        ":vivpar_hab",
        ":vph_autom",
        ":vph_inter",
        ":vph_pc",
    ]
    + [f":{col}" for col in SEGMENTO_DB_COLUMNS]
)

_UPDATE_SET_SQL = """
        geom = CASE WHEN EXCLUDED.geom IS NOT NULL THEN EXCLUDED.geom ELSE agebs_demografia.geom END,
        pobtot = CASE WHEN EXCLUDED.pobtot != -1 THEN EXCLUDED.pobtot ELSE agebs_demografia.pobtot END,
        pobmas = CASE WHEN EXCLUDED.pobmas != -1 THEN EXCLUDED.pobmas ELSE agebs_demografia.pobmas END,
        pobfem = CASE WHEN EXCLUDED.pobfem != -1 THEN EXCLUDED.pobfem ELSE agebs_demografia.pobfem END,
        vivtot = CASE WHEN EXCLUDED.vivtot != -1 THEN EXCLUDED.vivtot ELSE agebs_demografia.vivtot END,
        graproes = COALESCE(EXCLUDED.graproes, agebs_demografia.graproes),
        vivpar_hab = COALESCE(EXCLUDED.vivpar_hab, agebs_demografia.vivpar_hab),
        vph_autom = COALESCE(EXCLUDED.vph_autom, agebs_demografia.vph_autom),
        vph_inter = COALESCE(EXCLUDED.vph_inter, agebs_demografia.vph_inter),
        vph_pc = COALESCE(EXCLUDED.vph_pc, agebs_demografia.vph_pc)"""

for _col in SEGMENTO_DB_COLUMNS:
    _UPDATE_SET_SQL += f",\n        {_col} = COALESCE(EXCLUDED.{_col}, agebs_demografia.{_col})"

UPSERT_AGEB_SQL = f"""
    INSERT INTO agebs_demografia ({_INSERT_COLS_SQL})
    VALUES ({_INSERT_PARAMS_SQL})
    ON CONFLICT (cve_ageb)
    DO UPDATE SET {_UPDATE_SET_SQL};
"""

ENSURE_NSE_COLUMNS_SQL = """
    ALTER TABLE agebs_demografia
      ADD COLUMN IF NOT EXISTS graproes NUMERIC(6,2) DEFAULT NULL,
      ADD COLUMN IF NOT EXISTS vivpar_hab NUMERIC(8,2) DEFAULT NULL,
      ADD COLUMN IF NOT EXISTS vph_autom NUMERIC(8,2) DEFAULT NULL,
      ADD COLUMN IF NOT EXISTS vph_inter NUMERIC(8,2) DEFAULT NULL,
      ADD COLUMN IF NOT EXISTS vph_pc NUMERIC(8,2) DEFAULT NULL;
"""

ENSURE_SEGMENTO_COLUMNS_SQL = (
    "ALTER TABLE agebs_demografia\n"
    + ",\n".join(f"  ADD COLUMN IF NOT EXISTS {col} INTEGER DEFAULT NULL" for col in SEGMENTO_DB_COLUMNS)
    + ";"
)


def _num_or_none(value, *, as_int: bool = False):
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return None
    if as_int:
        return int(parsed)
    return float(parsed)


def _int_from_row(row, key: str) -> int:
    parsed = pd.to_numeric(row.get(key), errors="coerce")
    if pd.isna(parsed):
        return 0
    return int(parsed)


def _extraer_segmentos_censo(row) -> dict:
    segmentos: dict = {}
    for db_col, csv_col in SEGMENTO_CENSO_MAP:
        if csv_col:
            segmentos[db_col] = _int_from_row(row, csv_col)
        else:
            segmentos[db_col] = None

    pob15_64 = segmentos.get("pob15_64") or 0
    p1517 = (segmentos.get("p_15a17_f") or 0) + (segmentos.get("p_15a17_m") or 0)
    p1824 = (segmentos.get("p_18a24_f") or 0) + (segmentos.get("p_18a24_m") or 0)
    residual = max(0, pob15_64 - p1517 - p1824)
    pobfem = _int_from_row(row, "POBFEM")
    pobtot = _int_from_row(row, "POBTOT")
    ratio_f = (pobfem / pobtot) if pobtot > 0 else 0.5
    segmentos["p_25a59_f"] = int(round(residual * ratio_f))
    segmentos["p_25a59_m"] = residual - segmentos["p_25a59_f"]
    return segmentos


def censo_ageb_from_row(row) -> dict | None:
    """Extrae demografía + NSE + segmentos de una fila AGEB (MZA=0) del CSV INEGI."""
    try:
        ent = int(row["ENTIDAD"])
        mun = int(row["MUN"])
        loc = int(row["LOC"])
        ageb_code = str(row["AGEB"]).strip()
        if not ageb_code or ageb_code == "0000":
            return None

        cvegeo = f"{ent:02d}{mun:03d}{loc:04d}{ageb_code}"
        record = {
            "cve_ageb": cvegeo,
            "entidad": f"{ent:02d}",
            "municipio": f"{mun:03d}",
            "pobtot": _int_from_row(row, "POBTOT"),
            "pobmas": _int_from_row(row, "POBMAS"),
            "pobfem": _int_from_row(row, "POBFEM"),
            "vivtot": _int_from_row(row, "VIVTOT"),
            "graproes": _num_or_none(row.get("GRAPROES")),
            "vivpar_hab": _num_or_none(row.get("VIVPAR_HAB")),
            "vph_autom": _num_or_none(row.get("VPH_AUTOM"), as_int=True),
            "vph_inter": _num_or_none(row.get("VPH_INTER"), as_int=True),
            "vph_pc": _num_or_none(row.get("VPH_PC"), as_int=True),
        }
        record.update(_extraer_segmentos_censo(row))
        return record
    except Exception:
        return None


def merge_ageb_record(
    cvegeo: str,
    *,
    geom_data: dict | None,
    census_data: dict | None,
) -> dict:
    cvegeo = normalize_cvegeo(cvegeo) or cvegeo
    entidad = geom_data["entidad"] if geom_data else cvegeo[:2]
    municipio = geom_data["municipio"] if geom_data else cvegeo[2:5]
    wkt = geom_data.get("geom_wkt") if geom_data else None

    base = census_data or {}
    merged = {
        "cve_ageb": cvegeo,
        "entidad": entidad,
        "municipio": municipio,
        "wkt": wkt,
        "pobtot": base.get("pobtot", -1),
        "pobmas": base.get("pobmas", -1),
        "pobfem": base.get("pobfem", -1),
        "vivtot": base.get("vivtot", -1),
        "graproes": base.get("graproes"),
        "vivpar_hab": base.get("vivpar_hab"),
        "vph_autom": base.get("vph_autom"),
        "vph_inter": base.get("vph_inter"),
        "vph_pc": base.get("vph_pc"),
    }
    for col in SEGMENTO_DB_COLUMNS:
        merged[col] = base.get(col)
    return merged
