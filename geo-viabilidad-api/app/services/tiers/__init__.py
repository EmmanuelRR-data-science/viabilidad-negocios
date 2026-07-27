"""Registro y estrategias de tiers (basico / pro / premium)."""

from app.services.tiers.basico import BasicoTierStrategy
from app.services.tiers.premium import PremiumTierStrategy
from app.services.tiers.pro import ProTierStrategy
from app.services.tiers.registry import (
    check_feature_access,
    get_max_allies,
    get_max_competitors,
    get_pdf_pages,
    get_price,
    get_tier_details,
)

_STRATEGIES = {
    "basico": BasicoTierStrategy(),
    "pro": ProTierStrategy(),
    "premium": PremiumTierStrategy(),
}


def get_tier_strategy(tier_id: str):
    """Resuelve la estrategia de negocio del tier (fuente de verdad server-side)."""
    t_id = (tier_id or "").lower().strip()
    return _STRATEGIES.get(t_id, _STRATEGIES["basico"])


__all__ = [
    "BasicoTierStrategy",
    "ProTierStrategy",
    "PremiumTierStrategy",
    "check_feature_access",
    "get_max_allies",
    "get_max_competitors",
    "get_pdf_pages",
    "get_price",
    "get_tier_details",
    "get_tier_strategy",
]
