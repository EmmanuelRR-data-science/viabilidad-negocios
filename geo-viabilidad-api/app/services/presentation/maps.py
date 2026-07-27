"""
Genera la imagen del mapa para el PDF con la misma estética que el dashboard Leaflet:
tiles Carto Light, pin azul (ubicación), rojos (competencia) y verdes (aliados Premium).
"""

from __future__ import annotations

import io
import logging
import math

from PIL import Image, ImageDraw

from app.clients.v0.tiles import descargar_tile

logger = logging.getLogger("map_image")

TILE_SIZE = 256

COLOR_CENTRO = "#2563eb"
COLOR_COMPETIDOR = "#dc2626"
COLOR_ALIADO = "#10b981"
COLOR_RADIO_BORDE = (59, 130, 246, 200)
COLOR_RADIO_FILL = (59, 130, 246, 28)

MAP_WIDTH = 1280
MAP_HEIGHT = 800


def _lon_to_world_x(lon: float, zoom: int) -> float:
    return (lon + 180.0) / 360.0 * (2**zoom) * TILE_SIZE


def _lat_to_world_y(lat: float, zoom: int) -> float:
    lat_rad = math.radians(lat)
    return (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * (2**zoom) * TILE_SIZE


def _meters_to_lat_offset(meters: float) -> float:
    return meters / 111_320.0


def _meters_to_lng_offset(meters: float, lat: float) -> float:
    return meters / (111_320.0 * math.cos(math.radians(lat)))


def _bounds_latlng(
    lat: float,
    lng: float,
    radio: int,
    competidores: list,
    aliados: list | None,
) -> tuple[float, float, float, float]:
    pad = max(radio, 200) * 1.2
    dlat = _meters_to_lat_offset(pad)
    dlng = _meters_to_lng_offset(pad, lat)
    min_lat, max_lat = lat - dlat, lat + dlat
    min_lng, max_lng = lng - dlng, lng + dlng

    for punto in list(competidores or []) + list(aliados or []):
        plat, plng = punto.get("latitud"), punto.get("longitud")
        if plat is None or plng is None:
            continue
        min_lat = min(min_lat, float(plat))
        max_lat = max(max_lat, float(plat))
        min_lng = min(min_lng, float(plng))
        max_lng = max(max_lng, float(plng))

    return min_lat, max_lat, min_lng, max_lng


def _zoom_para_encajar(
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
    width: int,
    height: int,
) -> int:
    for zoom in range(18, 9, -1):
        x_span = abs(_lon_to_world_x(max_lng, zoom) - _lon_to_world_x(min_lng, zoom))
        y_span = abs(_lat_to_world_y(min_lat, zoom) - _lat_to_world_y(max_lat, zoom))
        if x_span <= width * 0.88 and y_span <= height * 0.88:
            return zoom
    return 12


def _fetch_tile(zoom: int, tile_x: int, tile_y: int) -> Image.Image | None:
    return descargar_tile(zoom, tile_x, tile_y)


def _render_base_map(
    center_lat: float,
    center_lng: float,
    zoom: int,
    width: int,
    height: int,
) -> tuple[Image.Image, float, float]:
    center_x = _lon_to_world_x(center_lng, zoom)
    center_y = _lat_to_world_y(center_lat, zoom)
    top_left_x = center_x - width / 2
    top_left_y = center_y - height / 2

    canvas = Image.new("RGBA", (width, height), (248, 250, 252, 255))
    n_tiles = 2**zoom
    tile_x0 = int(math.floor(top_left_x / TILE_SIZE))
    tile_y0 = int(math.floor(top_left_y / TILE_SIZE))
    tile_x1 = int(math.floor((top_left_x + width) / TILE_SIZE))
    tile_y1 = int(math.floor((top_left_y + height) / TILE_SIZE))

    for tile_x in range(tile_x0, tile_x1 + 1):
        for tile_y in range(tile_y0, tile_y1 + 1):
            if tile_x < 0 or tile_y < 0 or tile_x >= n_tiles or tile_y >= n_tiles:
                continue
            tile = _fetch_tile(zoom, tile_x, tile_y)
            if tile is None:
                continue
            paste_x = int(tile_x * TILE_SIZE - top_left_x)
            paste_y = int(tile_y * TILE_SIZE - top_left_y)
            canvas.paste(tile, (paste_x, paste_y))

    return canvas, top_left_x, top_left_y


def _latlng_a_pixel(
    lat: float,
    lng: float,
    zoom: int,
    top_left_x: float,
    top_left_y: float,
) -> tuple[float, float]:
    px = _lon_to_world_x(lng, zoom) - top_left_x
    py = _lat_to_world_y(lat, zoom) - top_left_y
    return px, py


def _dibujar_circulo_radio(
    overlay: Image.Image,
    lat: float,
    lng: float,
    radio: int,
    zoom: int,
    top_left_x: float,
    top_left_y: float,
) -> None:
    draw = ImageDraw.Draw(overlay, "RGBA")
    puntos: list[tuple[float, float]] = []
    for i in range(64):
        angulo = 2 * math.pi * i / 64
        p_lat = lat + _meters_to_lat_offset(radio * math.sin(angulo))
        p_lng = lng + _meters_to_lng_offset(radio * math.cos(angulo), lat)
        puntos.append(_latlng_a_pixel(p_lat, p_lng, zoom, top_left_x, top_left_y))
    draw.polygon(puntos, fill=COLOR_RADIO_FILL, outline=COLOR_RADIO_BORDE)


def _dibujar_pin(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    color: str,
    radio: int,
    borde: int = 2,
) -> None:
    bbox_ext = (x - radio - borde, y - radio - borde, x + radio + borde, y + radio + borde)
    bbox = (x - radio, y - radio, x + radio, y + radio)
    draw.ellipse(bbox_ext, fill="white")
    draw.ellipse(bbox, fill=color)


def generar_mapa_reporte(
    lat: float,
    lng: float,
    radio: int,
    competidores: list,
    aliados: list | None = None,
    *,
    incluir_aliados: bool = False,
    width: int = MAP_WIDTH,
    height: int = MAP_HEIGHT,
) -> bytes | None:
    """
    Mapa estático de alta resolución alineado con el dashboard (Carto + pines de color).
    """
    try:
        min_lat, max_lat, min_lng, max_lng = _bounds_latlng(lat, lng, radio, competidores, aliados)
        zoom = _zoom_para_encajar(min_lat, max_lat, min_lng, max_lng, width, height)
        center_lat = (min_lat + max_lat) / 2
        center_lng = (min_lng + max_lng) / 2

        base, top_left_x, top_left_y = _render_base_map(center_lat, center_lng, zoom, width, height)
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        _dibujar_circulo_radio(overlay, lat, lng, radio, zoom, top_left_x, top_left_y)

        draw = ImageDraw.Draw(overlay, "RGBA")

        if incluir_aliados and aliados:
            for aliado in aliados:
                a_lat, a_lng = aliado.get("latitud"), aliado.get("longitud")
                if a_lat is None or a_lng is None:
                    continue
                px, py = _latlng_a_pixel(float(a_lat), float(a_lng), zoom, top_left_x, top_left_y)
                _dibujar_pin(draw, px, py, COLOR_ALIADO, 6)

        for comp in competidores or []:
            c_lat, c_lng = comp.get("latitud"), comp.get("longitud")
            if c_lat is None or c_lng is None:
                continue
            px, py = _latlng_a_pixel(float(c_lat), float(c_lng), zoom, top_left_x, top_left_y)
            _dibujar_pin(draw, px, py, COLOR_COMPETIDOR, 6)

        px, py = _latlng_a_pixel(lat, lng, zoom, top_left_x, top_left_y)
        _dibujar_pin(draw, px, py, COLOR_CENTRO, 8, borde=3)

        composed = Image.alpha_composite(base, overlay).convert("RGB")
        buffer = io.BytesIO()
        composed.save(buffer, format="PNG", optimize=True)
        logger.info(
            "Mapa de reporte generado (%dx%d, zoom=%d, comp=%d, aliados=%d).",
            width,
            height,
            zoom,
            len(competidores or []),
            len(aliados or []) if incluir_aliados else 0,
        )
        return buffer.getvalue()
    except Exception as err:
        logger.error("Error generando mapa Carto para PDF: %s", err)
        return None
