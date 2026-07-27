from __future__ import annotations

from pydantic import BaseModel


class S3PresignedUrlDTO(BaseModel):
    """Respuesta cruda del SDK de boto3 al generar una presigned URL."""

    url: str
    bucket: str
    key: str
    expires_in: int
