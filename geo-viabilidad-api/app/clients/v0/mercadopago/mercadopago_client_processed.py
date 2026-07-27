"""Cliente Processed Mercado Pago: preferencias, pagos y webhooks tipados."""

from __future__ import annotations

import logging

from fastapi import Request

from app.clients.v0.mercadopago.mercadopago_client_raw import (
    app_base_url,
    checkout_return_base_valid,
    crear_preferencia_raw,
    obtener_merchant_order_raw,
    obtener_pago_raw,
)
from app.core.config import MERCADOPAGO_SANDBOX
from app.exceptions import ExternalDependencyError

logger = logging.getLogger("mercadopago_client_processed")


def crear_preferencia_checkout(
    checkout_id: str,
    monto: float,
    tier: str,
    payer_email: str | None,
    orden_id: int,
) -> str:
    base = app_base_url()
    preference_data: dict = {
        "items": [
            {
                "title": f"GeoViabilidad Hook - Reporte {tier.upper()}",
                "quantity": 1,
                "unit_price": float(monto),
                "currency_id": "MXN",
            }
        ],
        "external_reference": checkout_id,
        "statement_descriptor": "GEOVIABILIDAD",
    }

    if checkout_return_base_valid(base):
        preference_data["back_urls"] = {
            "success": f"{base}/?pago=ok&orden_id={orden_id}",
            "failure": f"{base}/?pago=error&orden_id={orden_id}",
            "pending": f"{base}/?pago=pending&orden_id={orden_id}",
        }
        preference_data["notification_url"] = f"{base}/api/pagos/webhook"
        preference_data["auto_return"] = "approved"
    else:
        logger.warning(
            "PUBLIC_APP_URL=%s no es HTTPS público; omitiendo back_urls/auto_return.",
            base,
        )

    if MERCADOPAGO_SANDBOX:
        preference_data["payment_methods"] = {
            "installments": 1,
            "default_installments": 1,
        }
        logger.info("Preferencia MP sandbox: checkout invitado (sin payer pre-cargado).")
    elif payer_email:
        preference_data["payer"] = {"email": payer_email}

    preference_response = crear_preferencia_raw(preference_data)
    response_body = preference_response.get("response") or {}
    if preference_response.get("status") not in (200, 201) or not response_body:
        mp_message = response_body.get("message") if isinstance(response_body, dict) else None
        logger.error("Mercado Pago preference error: %s", preference_response)
        detail = "No pudimos crear la preferencia de cobro en Mercado Pago."
        if mp_message:
            detail = f"{detail} ({mp_message})"
        raise ExternalDependencyError(detail, suggested_action="Intenta de nuevo en unos minutos.")

    if MERCADOPAGO_SANDBOX:
        init_point = response_body.get("sandbox_init_point")
        if not init_point:
            raise ExternalDependencyError(
                "Mercado Pago no devolvió el enlace sandbox de checkout.",
                suggested_action="Verifica la configuración sandbox e intenta de nuevo.",
            )
    else:
        init_point = response_body.get("init_point")
        if not init_point:
            raise ExternalDependencyError(
                "Mercado Pago no devolvió un enlace de checkout.",
                suggested_action="Intenta de nuevo en unos minutos.",
            )
    return init_point


def obtener_pago(payment_id: int) -> dict:
    payment_response = obtener_pago_raw(payment_id)
    response_body = payment_response.get("response") or {}
    if payment_response.get("status") not in (200, 201) or not response_body:
        logger.error("Mercado Pago payment lookup error for %s: %s", payment_id, payment_response)
        raise ExternalDependencyError(
            "No se pudo consultar el pago en Mercado Pago.",
            suggested_action="Espera unos segundos e intenta confirmar el pago nuevamente.",
        )
    return response_body


def obtener_merchant_order(merchant_order_id: int) -> dict:
    response = obtener_merchant_order_raw(merchant_order_id)
    body = response.get("response") or {}
    if response.get("status") not in (200, 201) or not body:
        logger.error("Mercado Pago merchant_order lookup error for %s: %s", merchant_order_id, response)
        raise ExternalDependencyError(
            "No se pudo consultar la orden de Mercado Pago.",
            suggested_action="Intenta de nuevo en unos minutos.",
        )
    return body


async def extraer_notificacion_webhook(request: Request) -> tuple[str | None, int | None]:
    topic = request.query_params.get("topic") or request.query_params.get("type")
    raw_id = request.query_params.get("data.id") or request.query_params.get("id")

    if request.method != "GET":
        payload: dict = {}
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if not payload:
            try:
                form = await request.form()
                payload = dict(form)
            except Exception:
                payload = {}
        if not topic:
            topic = payload.get("topic") or payload.get("type")
        if not raw_id:
            data = payload.get("data") or {}
            raw_id = data.get("id") if isinstance(data, dict) else payload.get("id")

    if raw_id is not None and str(raw_id).isdigit():
        return topic, int(raw_id)
    return topic, None


async def extraer_payment_id_webhook(request: Request) -> int | None:
    topic, raw_id = await extraer_notificacion_webhook(request)
    if raw_id is None:
        return None
    if topic == "merchant_order":
        try:
            merchant_order = obtener_merchant_order(raw_id)
        except ExternalDependencyError:
            return None
        payments = merchant_order.get("payments") or []
        for pay in reversed(payments):
            pid = pay.get("id") if isinstance(pay, dict) else None
            if pid is not None and str(pid).isdigit():
                return int(pid)
        return None
    return raw_id
