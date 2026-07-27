"""
CLI: ingesta nacional INEGI (32 estados) con variables NSE.
Uso (desde geo-viabilidad-api/): python scripts/ingest_inegi/ingest_all_states.py
"""

from __future__ import annotations

import os
import sys

import sqlalchemy
from geo_viabilidad_data.ingest_nacional import run_ingest_nacional

_API_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_MONOREPO_ROOT = os.path.dirname(_API_ROOT)

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://admin:admin_password_safe@127.0.0.1:5435/geoanalisis",
)
FUENTES_DIR = os.environ.get(
    "FUENTES_DIR",
    os.path.join(_MONOREPO_ROOT, "fuentes"),
)

print("=====================================================================")
print("GeoViabilidad Hook - Ingesta Nacional (censo + NSE)")
print("=====================================================================")

try:
    engine = sqlalchemy.create_engine(DB_URL)
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("SELECT 1"))
    print("Base de datos conectada.")
except Exception as exc:
    print(f"ERROR: No se pudo conectar a la base de datos: {exc}")
    sys.exit(1)

if not os.path.isdir(FUENTES_DIR):
    print(f"ERROR: Carpeta fuentes no encontrada: {FUENTES_DIR}")
    sys.exit(1)

print(f"Fuentes: {FUENTES_DIR}")
print("Iniciando ingesta de 32 estados (puede tardar varias horas)...")

try:
    resumen = run_ingest_nacional(engine, FUENTES_DIR)
except Exception as exc:
    print(f"ERROR en ingesta: {exc}")
    sys.exit(1)

print("\n=====================================================================")
print("INGESTA COMPLETADA")
print(f"  Estados procesados : {resumen['estados_procesados']}")
print(f"  Total AGEBs       : {resumen['total_agebs']:,}")
print(f"  Con geometría     : {resumen['agebs_con_geometria']:,}")
print(f"  Con NSE (GRAPROES): {resumen['agebs_con_nse']:,}")
print(f"  Con segmentos edad : {resumen.get('agebs_con_segmentos', 0):,}")
print("=====================================================================")
