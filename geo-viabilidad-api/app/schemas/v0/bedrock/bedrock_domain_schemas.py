from __future__ import annotations

from pydantic import BaseModel, Field


class BedrockFODADomain(BaseModel):
    fortalezas: list[str] = Field(default_factory=list)
    oportunidades: list[str] = Field(default_factory=list)
    debilidades: list[str] = Field(default_factory=list)
    amenazas: list[str] = Field(default_factory=list)
    consideraciones_apertura: list[str] = Field(default_factory=list)
    dictamen_final: str
    conclusion: str
    segmentacion_nicho: str
