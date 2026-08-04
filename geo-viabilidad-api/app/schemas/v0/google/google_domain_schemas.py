from __future__ import annotations

from pydantic import BaseModel, Field


class DireccionFisicaDomain(BaseModel):
    formato_completo: str | None = None
    calle: str | None = None
    numero: str | None = None
    colonia: str | None = None
    codigo_postal: str | None = None
    localidad: str | None = None
    estado: str | None = None


class LugarDomain(BaseModel):
    place_id: str
    nombre: str
    latitud: float
    longitud: float
    rating: float = 0.0
    user_ratings_total: int = 0
    direccion: str = ""
    google_types: list[str] = Field(default_factory=list)
    vigencia: dict = Field(default_factory=dict)
    distancia_metros: float | None = None
