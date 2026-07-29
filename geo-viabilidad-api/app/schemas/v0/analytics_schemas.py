from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SugerirAliadosRequest(BaseModel):
    rubro: str = Field(..., min_length=1)
    perfil_cliente: list[str] = Field(..., min_length=1, max_length=3)
    horarios_pico: list[str] = Field(..., min_length=1, max_length=2)


class GeocodificarResponse(BaseModel):
    status: str
    coordenadas: dict
    direccion: dict


class VistaPreviaResponse(BaseModel):
    """Contrato OpenAPI de la vista previa (campos adicionales se permiten)."""

    model_config = ConfigDict(extra="allow")

    status: str
    coordenadas: dict
    radio_metros: int
    rubro: str
    tier: str
    poblacion_estimada: int
    competidores_conteo: int
    score_viabilidad_sva: int
    score_demog: float
    score_competencia: float
    score_trafico: float
    densidad_hab_km2: float
    direccion: str
    competidores_listado: list[dict]
    competidores_destacados: list[dict]
    aliados_listado: list[dict]
    aliados_destacados: list[dict]
    atractores_seleccion: dict
    aliados_conteos: dict
    afluencia_peatonal: dict
    mensaje_tier: str


class ResultadoAnalisisResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    orden: dict
    metricas: dict
    analisis_estrategico_ia: dict


class BuscarDireccionResponse(BaseModel):
    status: str
    resultados: list[dict]


class SugerirAliadosResponse(BaseModel):
    status: str
    sugerencias: list | dict


class DebugCuantitativoResponse(BaseModel):
    status: str
    nota: str
    metricas: dict
