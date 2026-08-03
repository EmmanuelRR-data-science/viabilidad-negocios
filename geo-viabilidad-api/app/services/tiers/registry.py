"""Catálogo de precios y límites por tier (definitions.json).

La lógica de qué APIs/secciones aplica cada plan vive en
``services/tiers/{basico,pro,premium}.py``. El tier efectivo de un
reporte debe resolverse desde la orden de pago (servidor), no desde el body del cliente.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFINITIONS_PATH = Path(__file__).parent / "definitions.json"

_TIERS: dict[str, dict[str, Any]] = {}


def cargar_definitions() -> None:
    global _TIERS
    try:
        with open(_DEFINITIONS_PATH, encoding="utf-8") as f:
            _TIERS = json.load(f)
    except Exception:
        # Fallback predefinido si falla la lectura del archivo
        _TIERS = {
            "basico": {
                "name": "Básico",
                "price": 299.0,
                "max_competitors": 1,
                "max_allies": 0,
                "pdf_pages": 6,
                "features": [],
            },
            "pro": {
                "name": "Pro",
                "price": 649.0,
                "max_competitors": 3,
                "max_allies": 0,
                "pdf_pages": 10,
                "features": [],
            },
            "premium": {
                "name": "Premium",
                "price": 799.0,
                "max_competitors": 5,
                "max_allies": 5,
                "pdf_pages": 13,
                "features": ["aliados_guiados"],
            },
        }


# Cargar al importar
cargar_definitions()


def get_tier_details(tier_id: str) -> dict[str, Any]:
    """Retorna la configuración detallada de un tier."""
    t_id = (tier_id or "").lower().strip()
    if t_id not in _TIERS:
        # Si no se encuentra, retornar el básico como fallback seguro
        return _TIERS.get("basico", {})
    return _TIERS[t_id]


def check_feature_access(tier_id: str, feature_name: str) -> bool:
    """Verifica si un tier tiene acceso a una funcionalidad específica."""
    details = get_tier_details(tier_id)
    features = details.get("features", [])
    return feature_name in features


def get_price(tier_id: str) -> float:
    """Retorna el precio del tier."""
    return float(get_tier_details(tier_id).get("price", 0.0))


def get_max_competitors(tier_id: str) -> int:
    """Retorna el número máximo de competidores personalizados permitidos."""
    return int(get_tier_details(tier_id).get("max_competitors", 0))


def get_max_allies(tier_id: str) -> int:
    """Retorna el número máximo de aliados personalizados permitidos."""
    return int(get_tier_details(tier_id).get("max_allies", 0))


def get_pdf_pages(tier_id: str) -> int:
    """Retorna el número de páginas del PDF asociadas al tier."""
    return int(get_tier_details(tier_id).get("pdf_pages", 0))
