"""CLI: actualiza demografía + NSE desde CSVs INEGI (sin reprocesar shapefiles)."""

from __future__ import annotations

import os
import sys

import sqlalchemy

from app.ingest_nacional import run_ingest_censo_nacional

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://admin:admin_password_safe@127.0.0.1:5435/geoanalisis",
)
FUENTES_DIR = os.environ.get(
    "FUENTES_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "fuentes"),
)

print("Actualizando variables censales + NSE (32 estados)...")
engine = sqlalchemy.create_engine(DB_URL)
resumen = run_ingest_censo_nacional(engine, FUENTES_DIR)
print(
    f"Listo: {resumen['total_agebs']:,} AGEBs | "
    f"con NSE: {resumen['agebs_con_nse']:,} | "
    f"con segmentos: {resumen.get('agebs_con_segmentos', 0):,}"
)
