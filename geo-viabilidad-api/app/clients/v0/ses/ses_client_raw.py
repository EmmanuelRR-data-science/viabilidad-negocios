"""Cliente Raw de Amazon SES: envío de correo vía boto3."""

from __future__ import annotations

import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import AWS_REGION, SES_SENDER_EMAIL

logger = logging.getLogger("ses_client_raw")


def enviar_email_ses_raw(destinatario: str, subject: str, html_body: str) -> bool:
    """Envía un correo HTML vía Amazon SES. Retorna True si fue exitoso."""
    try:
        ses = boto3.client("ses", region_name=AWS_REGION)
        ses.send_email(
            Source=SES_SENDER_EMAIL,
            Destination={"ToAddresses": [destinatario]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
            },
        )
        logger.info("Correo SES enviado a %s", destinatario)
        return True
    except (BotoCoreError, ClientError) as err:
        logger.error("Error al enviar correo SES a %s: %s", destinatario, err)
        return False


def guardar_email_local(orden_id: int, html_body: str) -> str:
    """Guarda el HTML del correo en disco para desarrollo. Retorna la ruta."""
    os.makedirs("scratch/emails", exist_ok=True)
    path = f"scratch/emails/email_orden_{orden_id}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_body)
    logger.info("Email HTML guardado en %s", path)
    return path
