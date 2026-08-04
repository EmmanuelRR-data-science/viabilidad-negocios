import logging

import requests

from app.core.config import settings
from app.schemas.v0.google.google_dto_schemas import (
    GoogleGeocodeResponseDTO,
    GooglePlaceItemDTO,
)

logger = logging.getLogger("google_client_raw")


def _google_api_disponible() -> bool:
    return bool(
        settings.GOOGLE_MAPS_API_KEY
        and not settings.GOOGLE_MAPS_API_KEY.startswith("pega_tu")
        and "tu_token" not in settings.GOOGLE_MAPS_API_KEY
    )


def buscar_lugares_raw(
    lat: float,
    lng: float,
    radio: float,
    google_type: str,
    keyword: str | None = None,
) -> list[GooglePlaceItemDTO]:
    """Llamada directa a Google Places Nearby Search."""
    if not _google_api_disponible():
        logger.info("[RAW] Google API no disponible. Retornando lista vacía simulada.")
        return []

    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {"location": f"{lat},{lng}", "radius": radio, "type": google_type, "key": settings.GOOGLE_MAPS_API_KEY}
    if keyword:
        params["keyword"] = keyword

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") in ["OK", "ZERO_RESULTS"]:
            results = data.get("results", [])
            return [GooglePlaceItemDTO.model_validate(item) for item in results]
        else:
            status_err = data.get("status", "UNKNOWN_ERROR")
            raise Exception(f"Google Places Nearby Search falló con estatus: {status_err}")
    except Exception as e:
        logger.error(f"[RAW] Error en Nearby Search: {e}")
        raise e


def buscar_por_proximidad_raw(
    lat: float,
    lng: float,
    google_type: str,
) -> list[GooglePlaceItemDTO]:
    """Nearby Search ordenado por distancia (sin radio)."""
    if not _google_api_disponible():
        return []

    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "rankby": "distance",
        "type": google_type,
        "key": settings.GOOGLE_MAPS_API_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            return []
        return [GooglePlaceItemDTO.model_validate(item) for item in data.get("results", [])]
    except Exception as err:
        logger.warning("[RAW] Error en proximidad Places: %s", err)
        return []


def obtener_direccion_raw(lat: float, lng: float) -> GoogleGeocodeResponseDTO:
    """Geocodificación inversa mediante Google Geocoding API."""
    if not _google_api_disponible():
        return GoogleGeocodeResponseDTO(status="REQUEST_DENIED")

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"latlng": f"{lat},{lng}", "key": settings.GOOGLE_MAPS_API_KEY, "language": "es"}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return GoogleGeocodeResponseDTO.model_validate(data)
    except Exception as e:
        logger.error("[RAW] Error en geocodificación inversa: %s", e)
        return GoogleGeocodeResponseDTO(status="ERROR")


def buscar_coordenadas_por_direccion_raw(direccion: str) -> GoogleGeocodeResponseDTO:
    """Geocodificación directa mediante Google Geocoding API."""
    if not _google_api_disponible():
        return GoogleGeocodeResponseDTO(status="REQUEST_DENIED")

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": direccion,
        "key": settings.GOOGLE_MAPS_API_KEY,
        "language": "es",
        "components": "country:MX",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return GoogleGeocodeResponseDTO.model_validate(data)
    except Exception as e:
        logger.error("[RAW] Error en geocodificación directa: %s", e)
        return GoogleGeocodeResponseDTO(status="ERROR")


def obtener_mapa_estatico_raw(
    lat: float,
    lng: float,
    radio: int,
    competidores: list,
    aliados: list | None = None,
    *,
    incluir_aliados: bool = False,
) -> bytes | None:
    """Generación de mapa estático."""
    if not _google_api_disponible():
        return None

    url = "https://maps.googleapis.com/maps/api/staticmap"
    zoom = 14
    if radio <= 500:
        zoom = 15
    elif radio <= 1000:
        zoom = 14
    elif radio <= 3000:
        zoom = 13
    else:
        zoom = 12

    markers = [f"color:blue|label:O|{lat},{lng}"]

    comp_added = 0
    for comp in competidores:
        if comp_added >= 15:
            break
        c_lat = comp.get("latitud")
        c_lng = comp.get("longitud")
        if c_lat and c_lng:
            markers.append(f"color:red|{c_lat},{c_lng}")
            comp_added += 1

    if incluir_aliados and aliados:
        ally_added = 0
        for aliado in aliados:
            if ally_added >= 25:
                break
            a_lat = aliado.get("latitud")
            a_lng = aliado.get("longitud")
            if a_lat and a_lng:
                markers.append(f"color:green|{a_lat},{a_lng}")
                ally_added += 1

    marker_query = "&".join([f"markers={m}" for m in markers])
    style_query = "style=feature:poi.business|visibility:off"
    full_url = (
        f"{url}?center={lat},{lng}&zoom={zoom}&size=640x400&scale=2&maptype=roadmap"
        f"&key={settings.GOOGLE_MAPS_API_KEY}&{style_query}&{marker_query}"
    )

    try:
        response = requests.get(full_url, timeout=15)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"[RAW] Error al obtener mapa estático: {e}")
        return None
