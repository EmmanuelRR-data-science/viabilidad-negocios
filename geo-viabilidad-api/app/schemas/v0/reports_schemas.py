from __future__ import annotations

from pydantic import BaseModel


class DescargaPDFResponse(BaseModel):
    """Respuesta del servicio de reportes al router."""

    url_descarga: str
    validez_segundos: int
    orden_id: int
    checkout_id: str
