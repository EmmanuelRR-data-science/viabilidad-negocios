from __future__ import annotations

from pydantic import BaseModel, Field


class DescargaPDFResponse(BaseModel):
    """Respuesta del servicio de reportes al router."""

    url_descarga: str
    validez_segundos: int
    orden_id: int
    checkout_id: str


class ReportesPdfMetaResponse(BaseModel):
    """Metadatos de descarga expuestos por GET /api/reportes/pdf/{orden_id}."""

    status: str = "success"
    url_descarga: str
    validez_segundos: int
    orden_id: int
    checkout_id: str
    mensaje_seguridad: str = Field(
        ...,
        description="Aviso de vigencia del enlace de descarga.",
    )
