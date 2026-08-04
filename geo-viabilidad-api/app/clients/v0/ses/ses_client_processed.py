"""Cliente Processed de SES: envío tipado con fallback local en dev."""

from __future__ import annotations

import logging

from app.clients.v0.ses.ses_client_raw import enviar_email_ses_raw, guardar_email_local
from app.core.config import settings

logger = logging.getLogger("ses_client_processed")


def enviar_email_html(
    destinatario: str,
    subject: str,
    html_body: str,
    *,
    orden_id: int | None = None,
) -> bool:
    """Envía email o lo guarda localmente según settings.DEV_MODE."""
    if settings.DEV_MODE:
        logger.info("Modo desarrollo: guardando email localmente.")
        guardar_email_local(orden_id or 0, html_body)
        return True
    return enviar_email_ses_raw(destinatario, subject, html_body)
