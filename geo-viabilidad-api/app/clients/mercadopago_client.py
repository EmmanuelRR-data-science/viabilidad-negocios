"""DEPRECATED — use app.clients.v0.mercadopago instead.

This flat module is retained only for backward compatibility.
Hot-path code MUST import from ``app.clients.v0.mercadopago``.
"""

from app.clients.v0.mercadopago import (  # noqa: F401
    app_base_url,
    checkout_return_base_valid,
    crear_preferencia_checkout,
    extraer_notificacion_webhook,
    extraer_payment_id_webhook,
    get_sdk,
    obtener_merchant_order,
    obtener_pago,
)
