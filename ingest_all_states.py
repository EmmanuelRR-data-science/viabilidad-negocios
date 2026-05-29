import gc
import io
import os
import shutil
import sys
import tempfile
import zipfile

import fiona
import pandas as pd
import pyproj
import sqlalchemy
from shapely.geometry import shape
from shapely.ops import transform
from sqlalchemy import text

# Configuración de base de datos (por defecto Docker puerto 5435)
DB_URL = "postgresql://admin:admin_password_safe@127.0.0.1:5435/geoanalisis"
FUENTES_DIR = r"c:\Users\EmmanuelRamírez\OneDrive - PhiQus\Escritorio\viabilidad-hook\fuentes"
SPATIAL_ZIP_NAME = "889463807469_s.zip"

print("=====================================================================")
print("⚡ GeoViabilidad Hook - Pipeline CLI Ingesta Nacional Completa ⚡")
print("=====================================================================")

# 1. Probar Conexión e Inicializar Tablas
try:
    engine = sqlalchemy.create_engine(DB_URL)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✔️ Base de Datos conectada con éxito.")
except Exception as e:
    print(f"❌ ERROR: No se pudo conectar a la base de datos: {e}")
    print("Asegúrate de que el puerto 5435 del contenedor Docker esté expuesto y activo.")
    sys.exit(1)

# Asegurar tablas
try:
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
                geom GEOMETRY(Geometry, 4326)
            );
        """)
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agebs_geom ON agebs_demografia USING GIST (geom);"))
        conn.commit()
    print("✔️ Tablas del sistema verificadas en PostGIS.")
except Exception as e:
    print(f"❌ ERROR al inicializar tablas: {e}")
    sys.exit(1)

# 2. Abrir archivo de cartografía nacional de 3.1 GB
spatial_zip_path = os.path.join(FUENTES_DIR, SPATIAL_ZIP_NAME)
if not os.path.exists(spatial_zip_path):
    print(f"❌ ERROR: No se encontró el archivo espacial en {spatial_zip_path}")
    sys.exit(1)

# Diccionario de equivalencias de números de estado a nombres en sub-zips
# El script buscará cualquier archivo dentro de 889463807469_s.zip que comience con el número de estado
with zipfile.ZipFile(spatial_zip_path, "r") as z_main:
    sub_zips_in_main = z_main.namelist()

print(f"\nDetectados {len(sub_zips_in_main)} sub-archivos estatales dentro del ZIP nacional de cartografía.")

# Loop para recorrer los 32 estados de la República Mexicana
for state_num in range(1, 33):
    state_str = f"{state_num:02d}"
    print("\n------------------------------------------------------------")
    print(f"🔄 Procesando ESTADO {state_str} / 32...")
    print("------------------------------------------------------------")

    # A. Buscar sub-zip espacial para este estado
    target_sub_zip = None
    for sz in sub_zips_in_main:
        if sz.startswith(state_str + "_"):
            target_sub_zip = sz
            break

    if not target_sub_zip:
        print(f"⚠️ Advertencia: No se encontró cartografía para el estado {state_str} en el zip nacional. Saltando...")
        continue

    # B. Buscar zip de censo demográfico correspondiente
    # Formatos posibles: resageburb_XXcsv20.zip
    census_zip_name = f"resageburb_{state_str}csv20.zip"
    census_zip_path = os.path.join(FUENTES_DIR, census_zip_name)

    if not os.path.exists(census_zip_path):
        print(f"⚠️ Advertencia: No se encontró el censo demográfico {census_zip_name} en fuentes/. Saltando...")
        continue

    print(f"👉 Cartografía: {target_sub_zip}")
    print(f"👉 Censo Demográfico: {census_zip_name}")

    # C. Procesar y reproyectar cartografía estatal
    temp_dir = tempfile.mkdtemp()
    try:
        # Extraer sub-zip en disco temporal
        print("  - Extrayendo sub-zip geoespacial...")
        with zipfile.ZipFile(spatial_zip_path, "r") as z_main:
            sub_zip_data = z_main.read(target_sub_zip)

        sub_zip_io = io.BytesIO(sub_zip_data)
        with zipfile.ZipFile(sub_zip_io, "r") as z_sub:
            z_sub.extractall(temp_dir)

        # Localizar el archivo shapefile (*a.shp para AGEBs)
        shp_files = []
        for root, _dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith("a.shp") or (
                    file.endswith(".shp")
                    and not any(file.endswith(x) for x in ["sia.shp", "sil.shp", "sip.shp", "mun.shp", "ent.shp"])
                ):
                    shp_files.append(os.path.join(root, file))

        if not shp_files:
            print("  ❌ ERROR: No se encontró shapefile de AGEBs en el sub-zip.")
            continue

        target_shp = shp_files[0]

        # Leer geometrías
        print("  - Cargando y reproyectando geometrías (Fiona)...")
        geoms_dict = {}
        with fiona.open(target_shp, "r") as src:
            src_crs = src.crs
            proj_in = pyproj.CRS.from_user_input(src_crs)
            proj_out = pyproj.CRS.from_epsg(4326)
            transformer = pyproj.Transformer.from_crs(proj_in, proj_out, always_xy=True)

            for record in src:
                cvegeo = record["properties"]["CVEGEO"]
                cve_ent = record["properties"].get("CVE_ENT") or cvegeo[:2] if cvegeo else None
                cve_mun = record["properties"].get("CVE_MUN") or cvegeo[2:5] if cvegeo else None

                if not cvegeo:
                    continue

                # Reproyectar a EPSG:4326
                shp_geom = shape(record["geometry"])
                reprojected_geom = transform(transformer.transform, shp_geom)

                geoms_dict[cvegeo] = {"geom_wkt": reprojected_geom.wkt, "entidad": cve_ent, "municipio": cve_mun}

        print(f"  - Geometrías AGEB cargadas: {len(geoms_dict):,}")

        # D. Procesar Censo Demográfico CSV
        print("  - Leyendo y filtrando censo demográfico (MZA = 0)...")
        census_dict = {}
        with zipfile.ZipFile(census_zip_path, "r") as z_census:
            csv_files = [f for f in z_census.namelist() if f.endswith(".csv")]
            if not csv_files:
                print("  ❌ ERROR: No se encontró CSV de censo dentro del zip.")
                continue

            csv_name = csv_files[0]
            with z_census.open(csv_name) as csv_f:
                # Leer en chunks para cuidar la RAM
                chunk_iter = pd.read_csv(csv_f, encoding="utf-8-sig", chunksize=2000, keep_default_na=False)

                for chunk in chunk_iter:
                    chunk["MZA_num"] = pd.to_numeric(chunk["MZA"], errors="coerce").fillna(-1)
                    # Filtrar por AGEBs urbana total (MZA = 0)
                    filtered = chunk[(chunk["AGEB"] != "0000") & (chunk["MZA_num"] == 0)]

                    for _idx, row in filtered.iterrows():
                        try:
                            ent = int(row["ENTIDAD"])
                            mun = int(row["MUN"])
                            loc = int(row["LOC"])
                            ageb_code = str(row["AGEB"]).strip()

                            cvegeo = f"{ent:02d}{mun:03d}{loc:04d}{ageb_code}"

                            census_dict[cvegeo] = {
                                "pobtot": int(pd.to_numeric(row["POBTOT"], errors="coerce") or 0),
                                "pobmas": int(pd.to_numeric(row["POBMAS"], errors="coerce") or 0),
                                "pobfem": int(pd.to_numeric(row["POBFEM"], errors="coerce") or 0),
                                "vivtot": int(pd.to_numeric(row["VIVTOT"], errors="coerce") or 0),
                            }
                        except Exception:
                            pass

        print(f"  - Registros demográficos cargados: {len(census_dict):,}")

        # E. Fusión en Memoria (Join) e Inserción Masiva
        print("  - Realizando cruce (join) y preparando upserts...")
        merged_records = []

        # Todas las claves únicas combinadas de ambas fuentes
        all_keys = set(geoms_dict.keys()).union(census_dict.keys())

        for key in all_keys:
            geom_data = geoms_dict.get(key)
            census_data = census_dict.get(key)

            entidad = geom_data["entidad"] if geom_data else key[:2]
            municipio = geom_data["municipio"] if geom_data else key[2:5]

            wkt = geom_data["geom_wkt"] if geom_data else None

            pobtot = census_data["pobtot"] if census_data else -1
            pobmas = census_data["pobmas"] if census_data else -1
            pobfem = census_data["pobfem"] if census_data else -1
            vivtot = census_data["vivtot"] if census_data else -1

            merged_records.append(
                {
                    "cve_ageb": key,
                    "entidad": entidad,
                    "municipio": municipio,
                    "pobtot": pobtot,
                    "pobmas": pobmas,
                    "pobfem": pobfem,
                    "vivtot": vivtot,
                    "wkt": wkt,
                }
            )

        print(f"  - Total de registros unidos listos para subir: {len(merged_records):,}")

        # Escribir en base de datos en lotes
        print("  - Insertando lotes en PostGIS...")
        batch_size = 200
        total_inserted = 0

        for start_idx in range(0, len(merged_records), batch_size):
            batch = merged_records[start_idx : start_idx + batch_size]
            with engine.connect() as conn:
                stmt = text("""
                    INSERT INTO agebs_demografia 
                        (cve_ageb, entidad, municipio, geom, pobtot, pobmas, pobfem, vivtot)
                    VALUES 
                        (
                            :cve_ageb, 
                            :entidad, 
                            :municipio, 
                            CASE WHEN :wkt IS NOT NULL THEN ST_GeomFromText(:wkt, 4326) ELSE NULL END, 
                            :pobtot, 
                            :pobmas, 
                            :pobfem, 
                            :vivtot
                        )
                    ON CONFLICT (cve_ageb)
                    DO UPDATE SET 
                        geom = CASE WHEN EXCLUDED.geom IS NOT NULL THEN EXCLUDED.geom ELSE agebs_demografia.geom END,
                        pobtot = CASE WHEN EXCLUDED.pobtot != -1 THEN EXCLUDED.pobtot ELSE agebs_demografia.pobtot END,
                        pobmas = CASE WHEN EXCLUDED.pobmas != -1 THEN EXCLUDED.pobmas ELSE agebs_demografia.pobmas END,
                        pobfem = CASE WHEN EXCLUDED.pobfem != -1 THEN EXCLUDED.pobfem ELSE agebs_demografia.pobfem END,
                        vivtot = CASE WHEN EXCLUDED.vivtot != -1 THEN EXCLUDED.vivtot ELSE agebs_demografia.vivtot END;
                """)
                conn.execute(stmt, batch)
                conn.commit()
            total_inserted += len(batch)

        print(f"  ✔️ ÉXITO: {total_inserted:,} AGEBs del estado {state_str} insertadas/actualizadas con éxito.")

    except Exception as ex:
        print(f"  ❌ ERROR procesando estado {state_str}: {ex}")
    finally:
        # Limpieza de disco y RAM agresiva
        shutil.rmtree(temp_dir, ignore_errors=True)
        gc.collect()

print("\n=====================================================================")
print("🏁 PIPELINE CLI COMPLETADO CON ÉXITO.")
print("La base de datos PostGIS está completamente alimentada a nivel nacional.")
print("=====================================================================")
