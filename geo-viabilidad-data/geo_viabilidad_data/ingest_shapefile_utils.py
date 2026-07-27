"""Utilidades para detectar capas AGEB en shapefiles INEGI."""

from __future__ import annotations

import os
import re

from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import transform

# Capa urbana AGEB del Marco Geoestadístico: p.ej. 14a.shp, 01a.shp
_AGEB_SHP_RE = re.compile(r"^\d{2}a\.shp$", re.IGNORECASE)

CVEGEO_MAX_LEN = 13


def normalize_cvegeo(raw: str | None) -> str | None:
    """Normaliza CVEGEO de AGEB al formato estándar de 13 caracteres."""
    if raw is None:
        return None
    cve = str(raw).strip().upper()
    if len(cve) < 2:
        return None
    if len(cve) > CVEGEO_MAX_LEN:
        cve = cve[:CVEGEO_MAX_LEN]
    return cve


def is_ageb_shapefile(filename: str) -> bool:
    return bool(_AGEB_SHP_RE.match(os.path.basename(filename)))


def find_ageb_shapefile(root_dir: str) -> str | None:
    """Localiza el shapefile de AGEB urbano (*NNa.shp) dentro de un directorio."""
    matches: list[str] = []
    for root, _dirs, files in os.walk(root_dir):
        for file in files:
            if is_ageb_shapefile(file):
                matches.append(os.path.join(root, file))
    if not matches:
        return None
    return sorted(matches)[0]


def geom_wkt_from_fiona_feature(feat_geom, transformer) -> str | None:
    """Convierte geometría Fiona a WGS84 WKT; omite tipos que no son polígono de área."""
    shp_geom = shape(feat_geom)
    if not isinstance(shp_geom, (Polygon, MultiPolygon)) or shp_geom.is_empty:
        return None
    reprojected = transform(transformer.transform, shp_geom)
    return reprojected.wkt
