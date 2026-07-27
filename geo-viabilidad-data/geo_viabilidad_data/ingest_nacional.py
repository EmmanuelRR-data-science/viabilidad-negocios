"""
Ingesta nacional INEGI: cartografía AGEB + censo 2020 (incluye variables NSE).
Ejecutable desde CLI, Docker o panel admin.
"""

from __future__ import annotations

import gc
import io
import logging
import os
import shutil
import tempfile
import zipfile

import fiona
import pandas as pd
import pyproj
from sqlalchemy import text
from sqlalchemy.engine import Engine

from geo_viabilidad_data.ingest_censo_helpers import (
    ENSURE_NSE_COLUMNS_SQL,
    ENSURE_SEGMENTO_COLUMNS_SQL,
    UPSERT_AGEB_SQL,
    censo_ageb_from_row,
    merge_ageb_record,
)
from geo_viabilidad_data.ingest_shapefile_utils import (
    find_ageb_shapefile,
    geom_wkt_from_fiona_feature,
    normalize_cvegeo,
)

logger = logging.getLogger("ingest_nacional")

SPATIAL_ZIP_NAME = "889463807469_s.zip"


def ensure_ageb_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS agebs_demografia (
                id SERIAL PRIMARY KEY,
                cve_ageb VARCHAR(13) UNIQUE NOT NULL,
                entidad VARCHAR(2) NOT NULL,
                municipio VARCHAR(3) NOT NULL,
                pobtot INTEGER DEFAULT -1,
                pobmas INTEGER DEFAULT -1,
                pobfem INTEGER DEFAULT -1,
                vivtot INTEGER DEFAULT -1,
                graproes NUMERIC(6,2) DEFAULT NULL,
                vivpar_hab NUMERIC(8,2) DEFAULT NULL,
                vph_autom NUMERIC(8,2) DEFAULT NULL,
                vph_inter NUMERIC(8,2) DEFAULT NULL,
                vph_pc NUMERIC(8,2) DEFAULT NULL,
                geom GEOMETRY(Geometry, 4326)
            );
        """)
        )
        conn.execute(text(ENSURE_NSE_COLUMNS_SQL))
        conn.execute(text(ENSURE_SEGMENTO_COLUMNS_SQL))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agebs_geom ON agebs_demografia USING GIST (geom);"))
        conn.commit()


def _load_geoms_from_state_zip(spatial_zip_path: str, state_str: str) -> dict:
    geoms_dict: dict = {}
    with zipfile.ZipFile(spatial_zip_path, "r") as z_main:
        sub_zips = [n for n in z_main.namelist() if n.startswith(f"{state_str}_") and n.endswith(".zip")]
        if not sub_zips:
            return geoms_dict
        sub_zip_data = z_main.read(sub_zips[0])

    temp_dir = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(io.BytesIO(sub_zip_data), "r") as z_sub:
            z_sub.extractall(temp_dir)

        target_shp = find_ageb_shapefile(temp_dir)
        if not target_shp:
            return geoms_dict

        with fiona.open(target_shp, "r") as src:
            proj_in = pyproj.CRS.from_user_input(src.crs)
            proj_out = pyproj.CRS.from_epsg(4326)
            transformer = pyproj.Transformer.from_crs(proj_in, proj_out, always_xy=True)
            for record in src:
                cvegeo = normalize_cvegeo(record["properties"].get("CVEGEO"))
                if not cvegeo:
                    continue
                wkt = geom_wkt_from_fiona_feature(record["geometry"], transformer)
                if not wkt:
                    continue
                cve_ent = record["properties"].get("CVE_ENT") or cvegeo[:2]
                cve_mun = record["properties"].get("CVE_MUN") or cvegeo[2:5]
                geoms_dict[cvegeo] = {
                    "geom_wkt": wkt,
                    "entidad": cve_ent,
                    "municipio": cve_mun,
                }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return geoms_dict


def _normalize_census_columns(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk.columns = [str(c).replace("\ufeff", "").strip() for c in chunk.columns]
    return chunk


def _read_census_chunks(csv_f):
    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            csv_f.seek(0)
            for chunk in pd.read_csv(csv_f, encoding=encoding, chunksize=2000, keep_default_na=False):
                yield _normalize_census_columns(chunk)
            return
        except UnicodeDecodeError:
            continue
    csv_f.seek(0)
    for chunk in pd.read_csv(
        csv_f, encoding="latin-1", chunksize=2000, keep_default_na=False, encoding_errors="replace"
    ):
        yield _normalize_census_columns(chunk)


def _load_census_from_zip(census_zip_path: str) -> dict:
    census_dict: dict = {}
    with zipfile.ZipFile(census_zip_path, "r") as z_census:
        csv_files = [f for f in z_census.namelist() if f.endswith(".csv")]
        if not csv_files:
            return census_dict
        with z_census.open(csv_files[0]) as csv_f:
            for chunk in _read_census_chunks(csv_f):
                chunk["MZA_num"] = pd.to_numeric(chunk["MZA"], errors="coerce").fillna(-1)
                filtered = chunk[(chunk["AGEB"] != "0000") & (chunk["MZA_num"] == 0)]
                for _, row in filtered.iterrows():
                    parsed = censo_ageb_from_row(row)
                    if parsed:
                        census_dict[parsed["cve_ageb"]] = parsed
    return census_dict


def ingest_censo_state(engine: Engine, fuentes_dir: str, state_num: int) -> int:
    """Actualiza demografía + NSE desde CSV censal sin reprocesar cartografía."""
    state_str = f"{state_num:02d}"
    census_zip_path = os.path.join(fuentes_dir, f"resageburb_{state_str}csv20.zip")
    if not os.path.exists(census_zip_path):
        logger.warning("Sin censo para estado %s", state_str)
        return 0

    census_dict = _load_census_from_zip(census_zip_path)
    merged_records = [merge_ageb_record(key, geom_data=None, census_data=census_dict.get(key)) for key in census_dict]

    batch_size = 200
    total = 0
    for start_idx in range(0, len(merged_records), batch_size):
        batch = merged_records[start_idx : start_idx + batch_size]
        with engine.connect() as conn:
            conn.execute(text(UPSERT_AGEB_SQL), batch)
            conn.commit()
        total += len(batch)

    logger.info("Estado %s (solo censo): %s AGEBs upsert", state_str, total)
    gc.collect()
    return total


def ingest_state(engine: Engine, fuentes_dir: str, state_num: int, spatial_zip_path: str) -> int:
    state_str = f"{state_num:02d}"
    census_zip_path = os.path.join(fuentes_dir, f"resageburb_{state_str}csv20.zip")
    if not os.path.exists(census_zip_path):
        logger.warning("Sin censo para estado %s", state_str)
        return 0

    geoms_dict = _load_geoms_from_state_zip(spatial_zip_path, state_str)
    census_dict = _load_census_from_zip(census_zip_path)
    all_keys = set(geoms_dict.keys()).union(census_dict.keys())

    merged_records = [
        merge_ageb_record(
            key,
            geom_data=geoms_dict.get(key),
            census_data=census_dict.get(key),
        )
        for key in all_keys
    ]

    batch_size = 200
    total = 0
    for start_idx in range(0, len(merged_records), batch_size):
        batch = merged_records[start_idx : start_idx + batch_size]
        with engine.connect() as conn:
            conn.execute(text(UPSERT_AGEB_SQL), batch)
            conn.commit()
        total += len(batch)

    logger.info("Estado %s: %s AGEBs upsert", state_str, total)
    gc.collect()
    return total


def get_demografia_stats(engine: Engine) -> dict:
    with engine.connect() as conn:
        total_agebs = conn.execute(text("SELECT COUNT(*) FROM agebs_demografia")).scalar() or 0
        with_geom = conn.execute(text("SELECT COUNT(*) FROM agebs_demografia WHERE geom IS NOT NULL")).scalar() or 0
        with_nse = (
            conn.execute(
                text("SELECT COUNT(*) FROM agebs_demografia WHERE graproes IS NOT NULL AND graproes > 0")
            ).scalar()
            or 0
        )
        with_segmentos = (
            conn.execute(
                text("SELECT COUNT(*) FROM agebs_demografia WHERE pob0_14 IS NOT NULL AND pob0_14 >= 0")
            ).scalar()
            or 0
        )
    return {
        "total_agebs": int(total_agebs),
        "agebs_con_geometria": int(with_geom),
        "agebs_con_nse": int(with_nse),
        "agebs_con_segmentos": int(with_segmentos),
    }


def run_ingest_censo_nacional(
    engine: Engine,
    fuentes_dir: str,
    *,
    states: range | list[int] | None = None,
) -> dict:
    """Solo variables censales + NSE (rápido si la cartografía ya está cargada)."""
    ensure_ageb_schema(engine)
    state_list = list(states) if states is not None else list(range(1, 33))
    inserted = 0
    for state_num in state_list:
        inserted += ingest_censo_state(engine, fuentes_dir, state_num)
    stats = get_demografia_stats(engine)
    return {"estados_procesados": len(state_list), "registros_ultimo_lote": inserted, **stats}


def run_ingest_nacional(
    engine: Engine,
    fuentes_dir: str,
    *,
    states: range | list[int] | None = None,
) -> dict:
    """
    Ejecuta ingesta para 1..32 o lista de estados.
    Retorna resumen con totales y cobertura NSE.
    """
    ensure_ageb_schema(engine)
    spatial_zip_path = os.path.join(fuentes_dir, SPATIAL_ZIP_NAME)
    if not os.path.exists(spatial_zip_path):
        raise FileNotFoundError(f"No se encontró cartografía nacional: {spatial_zip_path}")

    state_list = list(states) if states is not None else list(range(1, 33))
    inserted = 0
    for state_num in state_list:
        inserted += ingest_state(engine, fuentes_dir, state_num, spatial_zip_path)

    stats = get_demografia_stats(engine)
    return {
        "estados_procesados": len(state_list),
        "registros_ultimo_lote": inserted,
        **stats,
    }
