from __future__ import annotations

from pydantic import BaseModel, Field


class AfluenciaDiaDomain(BaseModel):
    dia: str
    dia_int: int
    media: float
    maximo: float


class AfluenciaDomain(BaseModel):
    status: str
    venue_name: str | None = None
    afluencia_semanal: list[AfluenciaDiaDomain] = Field(default_factory=list)
    afluencia_horaria: list[float] = Field(default_factory=list)
    dia_pico: str | None = None
    hora_pico: str | None = None
    saturación_promedio: float = 0.0
