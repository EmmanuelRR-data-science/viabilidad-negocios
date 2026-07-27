"""Cliente Raw de tiles: descarga HTTP pura de tiles Carto."""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger("tiles_client_raw")

SUBDOMAINS = ("a", "b", "c", "d")
TILE_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"


def fetch_tile_bytes(zoom: int, tile_x: int, tile_y: int) -> bytes | None:
    """Descarga un tile PNG y retorna los bytes, o None si falla."""
    subdomain = SUBDOMAINS[(tile_x + tile_y) % len(SUBDOMAINS)]
    url = TILE_URL.format(s=subdomain, z=zoom, x=tile_x, y=tile_y)
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.content
    except Exception as err:
        logger.warning("No se pudo descargar tile %s/%s/%s: %s", zoom, tile_x, tile_y, err)
        return None
