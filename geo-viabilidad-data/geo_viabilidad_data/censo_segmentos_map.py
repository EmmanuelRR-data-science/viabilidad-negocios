"""Mapeo columnas BD ↔ CSV INEGI CPV 2020 (AGEB urbana, MZA=0)."""

from __future__ import annotations

# (columna_postgres, columna_csv_inegi)
SEGMENTO_CENSO_MAP: tuple[tuple[str, str], ...] = (
    ("pob0_14", "POB0_14"),
    ("pob15_64", "POB15_64"),
    ("pob65_mas", "POB65_MAS"),
    ("p_0a2_f", "P_0A2_F"),
    ("p_0a2_m", "P_0A2_M"),
    ("p_3a5_f", "P_3A5_F"),
    ("p_3a5_m", "P_3A5_M"),
    ("p_6a11_f", "P_6A11_F"),
    ("p_6a11_m", "P_6A11_M"),
    ("p_12a14_f", "P_12A14_F"),
    ("p_12a14_m", "P_12A14_M"),
    ("p_15a17_f", "P_15A17_F"),
    ("p_15a17_m", "P_15A17_M"),
    ("p_18a24_f", "P_18A24_F"),
    ("p_18a24_m", "P_18A24_M"),
    ("p_25a59_f", ""),  # derivado en ingesta (POB15_64 − 15-17 − 18-24)
    ("p_25a59_m", ""),
    ("p_60ymas_f", "P_60YMAS_F"),
    ("p_60ymas_m", "P_60YMAS_M"),
    ("pea", "PEA"),
    ("pea_f", "PEA_F"),
    ("pea_m", "PEA_M"),
    ("pocupada", "POCUPADA"),
    ("pocupada_f", "POCUPADA_F"),
    ("pocupada_m", "POCUPADA_M"),
    ("pdesocup", "PDESOCUP"),
    ("pdesocup_f", "PDESOCUP_F"),
    ("pdesocup_m", "PDESOCUP_M"),
    ("pe_inac", "PE_INAC"),
    ("pe_inac_f", "PE_INAC_F"),
    ("pe_inac_m", "PE_INAC_M"),
    ("p15a17a", "P15A17A"),
    ("p15a17a_f", "P15A17A_F"),
    ("p15a17a_m", "P15A17A_M"),
    ("p18a24a", "P18A24A"),
    ("p18a24a_f", "P18A24A_F"),
    ("p18a24a_m", "P18A24A_M"),
    ("p8a14an", "P8A14AN"),
    ("p8a14an_f", "P8A14AN_F"),
    ("p8a14an_m", "P8A14AN_M"),
)

SEGMENTO_DB_COLUMNS: tuple[str, ...] = tuple(col for col, _ in SEGMENTO_CENSO_MAP)

PIRAMIDE_GRUPOS: tuple[tuple[str, str, str], ...] = (
    ("0-2 años", "p_0a2_f", "p_0a2_m"),
    ("3-5 años", "p_3a5_f", "p_3a5_m"),
    ("6-11 años", "p_6a11_f", "p_6a11_m"),
    ("12-14 años", "p_12a14_f", "p_12a14_m"),
    ("15-17 años", "p_15a17_f", "p_15a17_m"),
    ("18-24 años", "p_18a24_f", "p_18a24_m"),
    ("25-59 años", "p_25a59_f", "p_25a59_m"),
    ("60+ años", "p_60ymas_f", "p_60ymas_m"),
)
