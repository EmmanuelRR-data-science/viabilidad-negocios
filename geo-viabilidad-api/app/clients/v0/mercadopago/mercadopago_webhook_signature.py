"""Validación de firma de webhooks Mercado Pago (x-signature)."""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import Request

from app.core.config import settings

logger = logging.getLogger("mercadopago_webhook_sig")


def _parse_x_signature(header: str) -> tuple[str | None, str | None]:
    """Extrae ts y v1 de 'ts=...,v1=...'."""
    ts = None
    v1 = None
    for part in header.split(","):
        part = part.strip()
        if part.startswith("ts="):
            ts = part[3:]
        elif part.startswith("v1="):
            v1 = part[3:]
    return ts, v1


def validar_firma_webhook_mp(request: Request) -> bool:
    """Valida x-signature según especificación de Mercado Pago.

    Si no hay `settings.MERCADOPAGO_WEBHOOK_SECRET`:
    - en settings.DEV_MODE se acepta (con warning) para demos locales;
    - en producción se rechaza.
    """
    secret = settings.MERCADOPAGO_WEBHOOK_SECRET
    if not secret:
        logger.error("Webhook MP rechazado: falta settings.MERCADOPAGO_WEBHOOK_SECRET.")
        return False

    x_signature = request.headers.get("x-signature") or request.headers.get("X-Signature")
    x_request_id = request.headers.get("x-request-id") or request.headers.get("X-Request-Id")
    if not x_signature:
        logger.warning("Webhook MP sin header x-signature.")
        return False

    ts, v1 = _parse_x_signature(x_signature)
    if not ts or not v1:
        logger.warning("Webhook MP x-signature malformado.")
        return False

    data_id = request.query_params.get("data.id") or request.query_params.get("id")
    manifest_parts: list[str] = []
    if data_id:
        manifest_parts.append(f"id:{str(data_id).lower()}")
    if x_request_id:
        manifest_parts.append(f"request-id:{x_request_id}")
    manifest_parts.append(f"ts:{ts}")
    manifest = ";".join(manifest_parts) + ";"

    digest = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    ok = hmac.compare_digest(digest, v1)
    if not ok:
        logger.warning("Webhook MP firma inválida (manifest=%s).", manifest)
    return ok
