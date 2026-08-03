from __future__ import annotations

from pydantic import BaseModel


class UrlDescargaSegura(BaseModel):
    """Datos de descarga que el servicio de reportes necesita del cliente de S3."""

    url: str
    validez_segundos: int
