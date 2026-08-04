import json
import logging

import requests
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.v0.besttime.besttime_dto_schemas import BestTimeForecastDTO

logger = logging.getLogger("besttime_client_raw")


def api_key_besttime_valida() -> bool:
    if (
        not settings.BESTTIME_API_KEY
        or settings.BESTTIME_API_KEY.startswith("pega_tu")
        or "tu_token" in settings.BESTTIME_API_KEY
    ):
        return False
    if settings.BESTTIME_API_KEY.startswith("pub_"):
        logger.error(
            "BestTime: la variable de entorno tiene la clave PÚBLICA (pub_...). "
            "Para generar forecasts de afluencia necesitas la clave PRIVADA (pri_...) "
            "desde https://besttime.app → Dashboard → API keys."
        )
        return False
    return True


def solicitar_forecast_besttime_raw(venue_name: str, venue_address: str) -> BestTimeForecastDTO:
    """Solicita un forecast a BestTime para un venue específico y devuelve el DTO crudo."""
    if not api_key_besttime_valida():
        return BestTimeForecastDTO(status="error", message="API Key de BestTime inválida o no configurada")

    url = "https://besttime.app/api/v1/forecasts"
    query_params = {
        "api_key_private": settings.BESTTIME_API_KEY,
        "venue_name": venue_name,
        "venue_address": venue_address,
    }

    try:
        response = requests.post(url, params=query_params, timeout=5)
        response.raise_for_status()
        data = response.json()
        return BestTimeForecastDTO.model_validate(data)
    except requests.exceptions.HTTPError as err:
        logger.error(f"[RAW] Error HTTP al invocar BestTime para '{venue_name}': {err}")
        status_code = err.response.status_code if err.response else "Unknown"
        return BestTimeForecastDTO(status="error", message=f"HTTP Error: {status_code}")
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as err:
        logger.warning(f"[RAW] Error de conexión/timeout con BestTime para '{venue_name}': {err}")
        return BestTimeForecastDTO(status="error", message="Timeout/Connection error")
    except json.JSONDecodeError as err:
        logger.error(f"[RAW] Respuesta de BestTime no es JSON válido para '{venue_name}': {err}")
        return BestTimeForecastDTO(status="error", message="Invalid JSON response")
    except ValidationError as err:
        logger.exception(f"[RAW] Error de validación de esquema en la respuesta de BestTime para '{venue_name}'")
        return BestTimeForecastDTO(status="error", message=f"Schema validation error: {err}")
    except Exception as err:
        logger.error(f"[RAW] Error inesperado en BestTime para '{venue_name}': {err}")
        return BestTimeForecastDTO(status="error", message=f"Unexpected error: {err}")
