import logging

import requests

from app.core.config import BESTTIME_API_KEY
from app.schemas.v0.besttime.besttime_dto_schemas import BestTimeForecastDTO

logger = logging.getLogger("besttime_client_raw")


def api_key_besttime_valida() -> bool:
    if not BESTTIME_API_KEY or BESTTIME_API_KEY.startswith("pega_tu") or "tu_token" in BESTTIME_API_KEY:
        return False
    if BESTTIME_API_KEY.startswith("pub_"):
        logger.error(
            "BestTime: la variable de entorno tiene la clave PÚBLICA (pub_...). "
            "Para generar forecasts de afluencia necesitas la clave PRIVADA (pri_...) "
            "desde https://besttime.app → Dashboard → API keys."
        )
        return False
    return True


def solicitar_forecast_besttime_raw(venue_name: str, venue_address: str) -> BestTimeForecastDTO | None:
    """Solicita un forecast a BestTime para un venue específico y devuelve el DTO crudo."""
    if not api_key_besttime_valida():
        return None

    url = "https://besttime.app/api/v1/forecasts"
    query_params = {
        "api_key_private": BESTTIME_API_KEY,
        "venue_name": venue_name,
        "venue_address": venue_address,
    }

    try:
        response = requests.post(url, params=query_params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return BestTimeForecastDTO.model_validate(data)
    except Exception as e:
        logger.warning(f"[RAW] BestTime falló para venue '{venue_name}': {e}")
        return None
