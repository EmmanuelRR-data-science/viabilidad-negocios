"""Cliente Raw de Amazon S3: operaciones puras boto3."""

from __future__ import annotations

import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.schemas.v0.s3.s3_dto_schemas import S3PresignedUrlDTO

logger = logging.getLogger("s3_client_raw")


def generar_presigned_url(
    bucket: str,
    key: str,
    filename: str,
    expires_in: int = 600,
) -> S3PresignedUrlDTO:
    client = boto3.client("s3", region_name=settings.AWS_REGION)
    url = client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=expires_in,
    )
    return S3PresignedUrlDTO(url=url, bucket=bucket, key=key, expires_in=expires_in)


def subir_objeto_s3(
    bucket: str,
    key: str,
    body: bytes,
    content_type: str = "application/pdf",
    *,
    sse: str = "aws:kms",
) -> bool:
    """Sube un objeto a S3 con encriptación server-side. Retorna True si fue exitoso."""
    try:
        client = boto3.client("s3", region_name=settings.AWS_REGION)
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            ServerSideEncryption=sse,
        )
        logger.info("Objeto subido a s3://%s/%s", bucket, key)
        return True
    except (BotoCoreError, ClientError) as err:
        logger.error("Error al subir a S3: %s", err)
        return False


def generar_presigned_url_simple(bucket: str, key: str, expires_in: int = 86400) -> str | None:
    """Genera URL pre-firmada sin ResponseContentDisposition."""
    try:
        client = boto3.client("s3", region_name=settings.AWS_REGION)
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
    except (BotoCoreError, ClientError) as err:
        logger.error("Error generando presigned URL para s3://%s/%s: %s", bucket, key, err)
        return None
