"""Cliente Processed de BD: modelos ORM tipados y queries tipadas para servicios."""

from __future__ import annotations

import logging

from geo_viabilidad_data.database import Base
from geo_viabilidad_data.models import AppUsuario, OrdenPago
from sqlalchemy.orm import Session

from app.clients.v0.database.database_client_raw import (
    query_columnas_nse_disponibles,
    query_columnas_segmentos_disponibles,
    query_demografia_ponderada,
    query_google_type,
    query_nse_censo,
    query_orden_por_id,
    query_segmentacion_demografica,
)

logger = logging.getLogger("database_client_processed")

__all__ = ["AppUsuario", "Base", "OrdenPago"]


# ---------------------------------------------------------------------------
# Demografía ponderada (retorno tipado)
# ---------------------------------------------------------------------------
def obtener_demografia_ponderada(db: Session, lat: float, lng: float, radio: int) -> dict:
    """Retorna demografía ponderada con claves limpias para servicios."""
    raw = query_demografia_ponderada(db, lat, lng, radio)
    if raw is None:
        logger.warning(
            "No se encontraron intersecciones de AGEBs en PostGIS para (%s, %s). "
            "Retornando 0 para reflejar la ausencia real de datos censales.",
            lat,
            lng,
        )
        return {
            "poblacion_ponderada": 0,
            "viviendas_ponderada": 0,
            "poblacion_masculina": 0,
            "poblacion_femenina": 0,
        }
    return {
        "poblacion_ponderada": int(round(raw["pobtot"])),
        "viviendas_ponderada": int(round(raw["vivtot"])),
        "poblacion_masculina": int(round(raw["pobmas"])),
        "poblacion_femenina": int(round(raw["pobfem"])),
    }


# ---------------------------------------------------------------------------
# Google Type resolver
# ---------------------------------------------------------------------------
_KEYWORD_FALLBACKS: list[tuple[str, tuple[str, str]]] = [
    ("cafe", ("cafe", "cafeteria")),
    ("farma", ("pharmacy", "farmacia")),
    ("restauran", ("restaurant", "restaurante")),
    ("comida", ("restaurant", "restaurante")),
    ("gym", ("gym", "gimnasio")),
    ("gimnasio", ("gym", "gimnasio")),
    ("veterinari", ("veterinary_care", "veterinaria")),
    ("veterinary", ("veterinary_care", "veterinaria")),
    ("mascota", ("pet_store", "accesorios_para_mascotas")),
    ("perro", ("pet_store", "accesorios_para_mascotas")),
    ("gato", ("pet_store", "accesorios_para_mascotas")),
    ("pet", ("pet_store", "accesorios_para_mascotas")),
    ("panaderia", ("bakery", "panaderia")),
    ("pan", ("bakery", "panaderia")),
    ("pasteler", ("bakery", "panaderia")),
    ("ropa", ("clothing_store", "tienda_de_ropa")),
    ("boutique", ("clothing_store", "tienda_de_ropa")),
    ("vestido", ("clothing_store", "tienda_de_ropa")),
    ("zapato", ("shoe_store", "zapateria")),
    ("calzado", ("shoe_store", "zapateria")),
    ("zapater", ("shoe_store", "zapateria")),
    ("juguete", ("toy_store", "jugueteria")),
    ("jugueter", ("toy_store", "jugueteria")),
    ("dentista", ("dentist", "dentista")),
    ("dental", ("dentist", "dentista")),
    ("odontolog", ("dentist", "dentista")),
    ("supermercado", ("supermarket", "supermercado")),
    ("super", ("supermarket", "supermercado")),
]


def resolver_google_type(db: Session, rubro: str) -> tuple[str, str]:
    """Resuelve el tipo Google Places con DB lookup + fallback por keywords."""
    from_db = query_google_type(db, rubro)
    if from_db:
        return from_db

    rub_lower = rubro.lower()
    for keyword, result in _KEYWORD_FALLBACKS:
        if keyword in rub_lower:
            return result
    return "store", "comercio_general"


# ---------------------------------------------------------------------------
# NSE — wrappers processed
# ---------------------------------------------------------------------------
def columnas_nse_disponibles(db: Session) -> bool:
    return query_columnas_nse_disponibles(db)


def consultar_nse_censo(db: Session, lat: float, lng: float, radio: int) -> dict | None:
    return query_nse_censo(db, lat, lng, radio)


# ---------------------------------------------------------------------------
# Segmentación demográfica — wrappers processed
# ---------------------------------------------------------------------------
def columnas_segmentos_disponibles(db: Session) -> bool:
    return query_columnas_segmentos_disponibles(db)


def consultar_segmentacion(db: Session, lat: float, lng: float, radio: int, columnas: list[str]) -> dict | None:
    return query_segmentacion_demografica(db, lat, lng, radio, columnas)


# ---------------------------------------------------------------------------
# OrdenPago
# ---------------------------------------------------------------------------
def obtener_orden_por_id(db: Session, orden_id: int) -> OrdenPago | None:
    return query_orden_por_id(db, orden_id)
