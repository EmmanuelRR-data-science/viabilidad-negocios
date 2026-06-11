"""Utilidades compartidas para ingesta censal INEGI 2020 por AGEB."""

from __future__ import annotations

import pandas as pd

NSE_CENSO_COLUMNS = ("GRAPROES", "VIVPAR_HAB", "VPH_AUTOM", "VPH_INTER", "VPH_PC")

REQUIRED_CENSO_COLUMNS = ("ENTIDAD", "MUN", "LOC", "AGEB", "MZA", "POBTOT", "POBFEM", "POBMAS", "VIVTOT")

UPSERT_AGEB_SQL = """
    INSERT INTO agebs_demografia
        (cve_ageb, entidad, municipio, geom, pobtot, pobmas, pobfem, vivtot,
         graproes, vivpar_hab, vph_autom, vph_inter, vph_pc)
    VALUES
        (
            :cve_ageb,
            :entidad,
            :municipio,
            CASE WHEN :wkt IS NOT NULL THEN ST_GeomFromText(:wkt, 4326) ELSE NULL END,
            :pobtot,
            :pobmas,
            :pobfem,
            :vivtot,
            :graproes,
            :vivpar_hab,
            :vph_autom,
            :vph_inter,
            :vph_pc
        )
    ON CONFLICT (cve_ageb)
    DO UPDATE SET
        geom = CASE WHEN EXCLUDED.geom IS NOT NULL THEN EXCLUDED.geom ELSE agebs_demografia.geom END,
        pobtot = CASE WHEN EXCLUDED.pobtot != -1 THEN EXCLUDED.pobtot ELSE agebs_demografia.pobtot END,
        pobmas = CASE WHEN EXCLUDED.pobmas != -1 THEN EXCLUDED.pobmas ELSE agebs_demografia.pobmas END,
        pobfem = CASE WHEN EXCLUDED.pobfem != -1 THEN EXCLUDED.pobfem ELSE agebs_demografia.pobfem END,
        vivtot = CASE WHEN EXCLUDED.vivtot != -1 THEN EXCLUDED.vivtot ELSE agebs_demografia.vivtot END,
        graproes = COALESCE(EXCLUDED.graproes, agebs_demografia.graproes),
        vivpar_hab = COALESCE(EXCLUDED.vivpar_hab, agebs_demografia.vivpar_hab),
        vph_autom = COALESCE(EXCLUDED.vph_autom, agebs_demografia.vph_autom),
        vph_inter = COALESCE(EXCLUDED.vph_inter, agebs_demografia.vph_inter),
        vph_pc = COALESCE(EXCLUDED.vph_pc, agebs_demografia.vph_pc);
"""

ENSURE_NSE_COLUMNS_SQL = """
    ALTER TABLE agebs_demografia
      ADD COLUMN IF NOT EXISTS graproes NUMERIC(6,2) DEFAULT NULL,
      ADD COLUMN IF NOT EXISTS vivpar_hab NUMERIC(8,2) DEFAULT NULL,
      ADD COLUMN IF NOT EXISTS vph_autom NUMERIC(8,2) DEFAULT NULL,
      ADD COLUMN IF NOT EXISTS vph_inter NUMERIC(8,2) DEFAULT NULL,
      ADD COLUMN IF NOT EXISTS vph_pc NUMERIC(8,2) DEFAULT NULL;
"""


def _num_or_none(value, *, as_int: bool = False):
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return None
    if as_int:
        return int(parsed)
    return float(parsed)


def censo_ageb_from_row(row) -> dict | None:
    """Extrae demografía + variables NSE de una fila AGEB (MZA=0) del CSV INEGI."""
    try:
        ent = int(row["ENTIDAD"])
        mun = int(row["MUN"])
        loc = int(row["LOC"])
        ageb_code = str(row["AGEB"]).strip()
        if not ageb_code or ageb_code == "0000":
            return None

        cvegeo = f"{ent:02d}{mun:03d}{loc:04d}{ageb_code}"
        record = {
            "cve_ageb": cvegeo,
            "entidad": f"{ent:02d}",
            "municipio": f"{mun:03d}",
            "pobtot": int(pd.to_numeric(row["POBTOT"], errors="coerce") or 0),
            "pobmas": int(pd.to_numeric(row["POBMAS"], errors="coerce") or 0),
            "pobfem": int(pd.to_numeric(row["POBFEM"], errors="coerce") or 0),
            "vivtot": int(pd.to_numeric(row["VIVTOT"], errors="coerce") or 0),
            "graproes": _num_or_none(row.get("GRAPROES")),
            "vivpar_hab": _num_or_none(row.get("VIVPAR_HAB")),
            "vph_autom": _num_or_none(row.get("VPH_AUTOM"), as_int=True),
            "vph_inter": _num_or_none(row.get("VPH_INTER"), as_int=True),
            "vph_pc": _num_or_none(row.get("VPH_PC"), as_int=True),
        }
        return record
    except Exception:
        return None


def merge_ageb_record(
    cvegeo: str,
    *,
    geom_data: dict | None,
    census_data: dict | None,
) -> dict:
    entidad = geom_data["entidad"] if geom_data else cvegeo[:2]
    municipio = geom_data["municipio"] if geom_data else cvegeo[2:5]
    wkt = geom_data.get("geom_wkt") if geom_data else None

    base = census_data or {}
    return {
        "cve_ageb": cvegeo,
        "entidad": entidad,
        "municipio": municipio,
        "wkt": wkt,
        "pobtot": base.get("pobtot", -1),
        "pobmas": base.get("pobmas", -1),
        "pobfem": base.get("pobfem", -1),
        "vivtot": base.get("vivtot", -1),
        "graproes": base.get("graproes"),
        "vivpar_hab": base.get("vivpar_hab"),
        "vph_autom": base.get("vph_autom"),
        "vph_inter": base.get("vph_inter"),
        "vph_pc": base.get("vph_pc"),
    }
