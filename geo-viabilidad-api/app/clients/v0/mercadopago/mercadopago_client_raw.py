"""Cliente Raw Mercado Pago: SDK y llamadas HTTP puras."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from app.core.config import MERCADOPAGO_ACCESS_TOKEN, PUBLIC_APP_URL
from app.exceptions import ExternalDependencyError

logger = logging.getLogger("mercadopago_client_raw")


def get_sdk():
    if not MERCADOPAGO_ACCESS_TOKEN:
        raise ExternalDependencyError(
            "Mercado Pago no está configurado en el servidor.",
            suggested_action="Contacta al administrador para habilitar los cobros.",
            status_code=503,
        )
    import mercadopago

    return mercadopago.SDK(MERCADOPAGO_ACCESS_TOKEN)


def app_base_url() -> str:
    base = (PUBLIC_APP_URL or "").strip().rstrip("/")
    if not base:
        raise ExternalDependencyError(
            "PUBLIC_APP_URL no está configurada. Requerida para Checkout Pro y webhooks.",
            suggested_action="Configura la URL pública HTTPS de la aplicación.",
            status_code=503,
        )
    return base


def checkout_return_base_valid(base: str | None = None) -> bool:
    url = (base if base is not None else app_base_url()).strip().rstrip("/")
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        return False
    if host.startswith("192.168.") or host.startswith("10.") or host.startswith("172."):
        return False
    return True


def crear_preferencia_raw(preference_data: dict) -> dict:
    sdk = get_sdk()
    return sdk.preference().create(preference_data)


def obtener_pago_raw(payment_id: int) -> dict:
    sdk = get_sdk()
    return sdk.payment().get(payment_id)


def obtener_merchant_order_raw(merchant_order_id: int) -> dict:
    sdk = get_sdk()
    return sdk.merchant_order().get(merchant_order_id)
