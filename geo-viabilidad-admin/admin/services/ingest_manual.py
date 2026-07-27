"""Ingesta manual de cartografía shapefile y censo CSV (ZIP)."""

from __future__ import annotations

import gc
import io
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field

import fiona
import pandas as pd
import pyproj
from geo_viabilidad_data.ingest_censo_helpers import UPSERT_AGEB_SQL, censo_ageb_from_row
from geo_viabilidad_data.ingest_shapefile_utils import (
    find_ageb_shapefile,
    geom_wkt_from_fiona_feature,
    normalize_cvegeo,
)
from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass
class IngestResult:
    success: bool
    message: str
    inserted_count: int = 0
    logs: list[str] = field(default_factory=list)


def _find_ageb_shapefiles(root_dir: str) -> list[str]:
    target = find_ageb_shapefile(root_dir)
    return [target] if target else []


def ingest_shapefile_zip(engine: Engine, zip_bytes: bytes, filename: str) -> IngestResult:
    logs: list[str] = []

    def log(msg: str) -> None:
        logs.append(msg)

    log(f"Iniciando procesamiento de {filename}...")
    temp_dir = tempfile.mkdtemp()
    inserted_count = 0

    try:
        zip_path = os.path.join(temp_dir, "uploaded_shp.zip")
        with open(zip_path, "wb") as f_zip:
            f_zip.write(zip_bytes)

        extract_path = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_path, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)

        shp_files = _find_ageb_shapefiles(extract_path)
        if not shp_files:
            return IngestResult(
                success=False,
                message="No se detectó un shapefile de AGEBs válido (*a.shp).",
                logs=logs + ["ERROR: shapefile AGEB no encontrado en el ZIP."],
            )

        target_shp = shp_files[0]
        log(f"Shapefile detectado: {os.path.basename(target_shp)}")

        with fiona.open(target_shp, "r") as src:
            proj_in = pyproj.CRS.from_user_input(src.crs)
            proj_out = pyproj.CRS.from_epsg(4326)
            transformer = pyproj.Transformer.from_crs(proj_in, proj_out, always_xy=True)
            features = list(src)
            total_features = len(features)
            log(f"Total de AGEBs a procesar: {total_features}")

            batch_size = 100
            batch_data: list[dict] = []
            batch_errors = 0
            skipped_non_polygon = 0

            for idx, feat in enumerate(features):
                cvegeo = normalize_cvegeo(feat["properties"].get("CVEGEO"))
                if not cvegeo:
                    continue
                cve_ent = feat["properties"].get("CVE_ENT") or cvegeo[:2]
                cve_mun = feat["properties"].get("CVE_MUN") or cvegeo[2:5]
                wkt = geom_wkt_from_fiona_feature(feat["geometry"], transformer)
                if not wkt:
                    skipped_non_polygon += 1
                    continue
                batch_data.append(
                    {
                        "cve_ageb": cvegeo,
                        "entidad": cve_ent,
                        "municipio": cve_mun,
                        "wkt": wkt,
                    }
                )

                if len(batch_data) >= batch_size or idx == total_features - 1:
                    if not batch_data:
                        continue
                    try:
                        with engine.connect() as conn:
                            stmt = text("""
                                INSERT INTO agebs_demografia
                                    (cve_ageb, entidad, municipio, geom, pobtot, pobmas, pobfem, vivtot)
                                VALUES
                                    (:cve_ageb, :entidad, :municipio, ST_GeomFromText(:wkt, 4326), -1, -1, -1, -1)
                                ON CONFLICT (cve_ageb)
                                DO UPDATE SET
                                    geom = EXCLUDED.geom,
                                    entidad = EXCLUDED.entidad,
                                    municipio = EXCLUDED.municipio;
                            """)
                            conn.execute(stmt, batch_data)
                            conn.commit()
                        inserted_count += len(batch_data)
                        batch_data = []
                    except Exception as batch_err:
                        batch_errors += 1
                        log(f"Error en lote ({len(batch_data)} registros): {batch_err}")
                        batch_data = []

            if skipped_non_polygon:
                log(f"Geometrías omitidas (no son polígono de área): {skipped_non_polygon:,}")
            if batch_errors:
                log(f"Lotes con error: {batch_errors}")
            if inserted_count == 0:
                return IngestResult(
                    success=False,
                    message="No se insertó ninguna geometría. Revisa el log de la ingesta.",
                    inserted_count=0,
                    logs=logs,
                )

        log(f"Proceso finalizado. Geometrías insertadas/actualizadas: {inserted_count:,}")
        return IngestResult(
            success=True,
            message=f"Se cargaron {inserted_count:,} polígonos geoespaciales.",
            inserted_count=inserted_count,
            logs=logs,
        )
    except Exception as err:
        log(f"ERROR CRÍTICO: {err}")
        return IngestResult(
            success=False,
            message=(
                "La ingesta de cartografía no se pudo completar. "
                "Revisa el formato del ZIP y que el esquema AGEB esté inicializado."
            ),
            inserted_count=inserted_count,
            logs=logs,
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        gc.collect()


def ingest_census_zip(engine: Engine, zip_bytes: bytes, filename: str) -> IngestResult:
    logs: list[str] = []

    def log(msg: str) -> None:
        logs.append(msg)

    log(f"Abriendo archivo demográfico {filename}...")
    inserted_count = 0

    try:
        zip_data = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(zip_data, "r") as z:
            csv_files = [name for name in z.namelist() if name.endswith(".csv")]
            if not csv_files:
                return IngestResult(
                    success=False,
                    message="No se encontró archivo CSV dentro del ZIP.",
                    logs=logs + ["ERROR: CSV de censo no encontrado."],
                )

            csv_target = csv_files[0]
            log(f"CSV detectado: {csv_target}")

            chunk_iter = pd.read_csv(z.open(csv_target), encoding="utf-8-sig", chunksize=2000, keep_default_na=False)
            mapped_records: list[dict] = []
            total_processed_rows = 0

            for chunk in chunk_iter:
                total_processed_rows += len(chunk)
                chunk["MZA_num"] = pd.to_numeric(chunk["MZA"], errors="coerce").fillna(-1)
                filtered = chunk[(chunk["AGEB"] != "0000") & (chunk["MZA_num"] == 0)]
                for _, row in filtered.iterrows():
                    parsed = censo_ageb_from_row(row)
                    if not parsed:
                        continue
                    mapped_records.append({**parsed, "wkt": None})

            total_mapped = len(mapped_records)
            log(f"Filas CSV leídas: {total_processed_rows:,}")
            log(f"AGEBs válidas con demografía: {total_mapped:,}")

            batch_size = 100
            for start_idx in range(0, total_mapped, batch_size):
                batch = mapped_records[start_idx : start_idx + batch_size]
                with engine.connect() as conn:
                    conn.execute(text(UPSERT_AGEB_SQL), batch)
                    conn.commit()
                inserted_count += len(batch)

        log(f"Proceso finalizado. Registros demográficos upsert: {inserted_count:,}")
        return IngestResult(
            success=True,
            message=f"Se cargaron datos demográficos de {inserted_count:,} AGEBs.",
            inserted_count=inserted_count,
            logs=logs,
        )
    except Exception as err:
        log(f"ERROR CRÍTICO: {err}")
        return IngestResult(
            success=False,
            message=(
                "La ingesta demográfica (censo) no se pudo completar. "
                "Revisa que el ZIP contenga el CSV INEGI esperado y que el esquema esté listo."
            ),
            inserted_count=inserted_count,
            logs=logs,
        )
    finally:
        gc.collect()


def ingest_nacional_all_states(engine: Engine, fuentes_dir: str) -> IngestResult:
    from geo_viabilidad_data.ingest_nacional import ensure_ageb_schema, get_demografia_stats, ingest_state

    logs: list[str] = []

    def log(msg: str) -> None:
        logs.append(msg)

    spatial_zip = os.path.join(fuentes_dir, "889463807469_s.zip")
    if not os.path.exists(spatial_zip):
        return IngestResult(
            success=False,
            message=f"No se encontró cartografía nacional en {spatial_zip}",
            logs=logs,
        )

    log("Iniciando ingesta nacional de 32 estados...")
    total_inserted = 0

    try:
        ensure_ageb_schema(engine)
        for state_num in range(1, 33):
            state_str = f"{state_num:02d}"
            log(f"Procesando estado {state_str}/32...")
            try:
                count = ingest_state(engine, fuentes_dir, state_num, spatial_zip)
                total_inserted += count
                log(f"  Estado {state_str}: {count:,} AGEBs upsert.")
            except Exception as state_err:
                log(f"  Error en estado {state_str}: {state_err}")
            gc.collect()

        resumen = get_demografia_stats(engine)
        log(f"Ingesta completada. Total AGEBs: {resumen['total_agebs']:,} | Con NSE: {resumen['agebs_con_nse']:,}")
        return IngestResult(
            success=True,
            message="Base de datos nacional alimentada con variables NSE.",
            inserted_count=total_inserted,
            logs=logs,
        )
    except Exception as err:
        log(f"ERROR GENERAL: {err}")
        return IngestResult(
            success=False,
            message=(
                "La ingesta nacional no se pudo completar. "
                "Verifica la carpeta de fuentes por estado y la conexión a la base de datos."
            ),
            inserted_count=total_inserted,
            logs=logs,
        )
    finally:
        gc.collect()
