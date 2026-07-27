"""CLI: actualiza demografía + NSE desde CSVs INEGI (sin reprocesar shapefiles).

Uso (desde geo-viabilidad-api/): python scripts/ingest_inegi/ingest_censo_nse.py
"""

from __future__ import annotations

import os

import sqlalchemy
from geo_viabilidad_data.ingest_nacional import run_ingest_censo_nacional

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

print("Actualizando variables censales + NSE (32 estados)...")
engine = sqlalchemy.create_engine(DB_URL)
resumen = run_ingest_censo_nacional(engine, FUENTES_DIR)
print(
    f"Listo: {resumen['total_agebs']:,} AGEBs | "
    f"con NSE: {resumen['agebs_con_nse']:,} | "
    f"con segmentos: {resumen.get('agebs_con_segmentos', 0):,}"
)
