"""Estado de fuentes INEGI y cobertura demográfica en base de datos."""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.ingest_nacional import SPATIAL_ZIP_NAME, get_demografia_stats


@dataclass
class FuentesStatus:
    fuentes_dir: str
    cartografia_ok: bool
    cartografia_path: str
    census_files: int
    census_ready: bool


@dataclass
class IngestDashboardStats:
    total_agebs: int
    con_geom: int
    con_censo: int
    con_nse: int
    estados: list[dict]


def resolve_fuentes_dir(custom_dir: str | None = None) -> str:
    if custom_dir:
        return custom_dir
    env_dir = os.environ.get("FUENTES_DIR", "").strip()
    if env_dir:
        return env_dir
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(repo_root, "fuentes")


def fetch_fuentes_status(fuentes_dir: str | None = None) -> FuentesStatus:
    base = resolve_fuentes_dir(fuentes_dir)
    cartografia_path = os.path.join(base, SPATIAL_ZIP_NAME)
    cartografia_ok = os.path.exists(cartografia_path)

    census_files = 0
    if os.path.isdir(base):
        census_files = sum(
            1 for name in os.listdir(base) if name.startswith("resageburb_") and name.endswith("csv20.zip")
        )

    return FuentesStatus(
        fuentes_dir=base,
        cartografia_ok=cartografia_ok,
        cartografia_path=cartografia_path,
        census_files=census_files,
        census_ready=census_files >= 32,
    )


def fetch_ingest_dashboard_stats(engine: Engine) -> IngestDashboardStats:
    base_stats = get_demografia_stats(engine)
    con_censo = 0
    estados: list[dict] = []

    try:
        with engine.connect() as conn:
            con_censo = conn.execute(text("SELECT count(*) FROM agebs_demografia WHERE pobtot != -1")).scalar() or 0
            res = conn.execute(
                text("""
                SELECT entidad,
                       count(*) as total,
                       count(geom) as con_geom,
                       count(CASE WHEN pobtot != -1 THEN 1 END) as con_censo
                FROM agebs_demografia
                GROUP BY entidad
                ORDER BY entidad
            """)
            )
            estados = [dict(row._mapping) for row in res]
    except Exception:
        pass

    return IngestDashboardStats(
        total_agebs=base_stats["total_agebs"],
        con_geom=base_stats["agebs_con_geometria"],
        con_censo=int(con_censo),
        con_nse=base_stats["agebs_con_nse"],
        estados=estados,
    )
