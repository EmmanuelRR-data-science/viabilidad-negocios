from typing import TypedDict


class NSEMetricasRaw(TypedDict):
    escolaridad_promedio: float
    internet_pct: float
    autos_pct: float
    pc_pct: float
    fuente: str


class NSEDiagnostico(TypedDict):
    nse_score: float
    nse_etiqueta: str
    metricas: NSEMetricasRaw
    agebs_consultadas: int
