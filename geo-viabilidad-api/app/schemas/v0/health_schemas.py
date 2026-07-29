"""Esquemas HTTP de salud / diagnóstico."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Respuesta pública de liveness (sin flags de entorno)."""

    status: str = Field("ok", description="Estado del servicio")
    service: str = Field(..., description="Nombre del servicio")
    timestamp: str = Field(..., description="Marca de tiempo ISO-8601 UTC")
