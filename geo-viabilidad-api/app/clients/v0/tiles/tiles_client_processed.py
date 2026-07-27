"""Cliente Processed de tiles: retorna PIL Image."""

from __future__ import annotations

import io
import logging

from PIL import Image

from app.clients.v0.tiles.tiles_client_raw import fetch_tile_bytes

logger = logging.getLogger("tiles_client_processed")


def descargar_tile(zoom: int, tile_x: int, tile_y: int) -> Image.Image | None:
    """Descarga un tile y retorna como PIL RGBA Image, o None."""
    raw = fetch_tile_bytes(zoom, tile_x, tile_y)
    if raw is None:
        return None
    return Image.open(io.BytesIO(raw)).convert("RGBA")
