"""Cliente de base de datos (PostGIS) — raw (sesión) + processed (modelos)."""

from app.clients.v0.database.database_client_processed import (
    AppUsuario,
    OrdenPago,
    columnas_nse_disponibles,
    columnas_segmentos_disponibles,
    consultar_nse_censo,
    consultar_segmentacion,
    obtener_demografia_ponderada,
    obtener_orden_por_id,
    resolver_google_type,
)
from app.clients.v0.database.database_client_raw import Base, SessionLocal, engine, get_db

__all__ = [
    "AppUsuario",
    "Base",
    "OrdenPago",
    "SessionLocal",
    "columnas_nse_disponibles",
    "columnas_segmentos_disponibles",
    "consultar_nse_censo",
    "consultar_segmentacion",
    "engine",
    "get_db",
    "obtener_demografia_ponderada",
    "obtener_orden_por_id",
    "resolver_google_type",
]
