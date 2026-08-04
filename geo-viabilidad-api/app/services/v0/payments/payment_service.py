"""Lógica de negocio: órdenes de pago, webhooks y Checkout Pro."""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.clients.v0.database import OrdenPago
from app.clients.v0.mercadopago import (
    checkout_return_base_valid,
    crear_preferencia_checkout,
    extraer_payment_id_webhook,
    obtener_pago,
)
from app.core.config import settings
from app.core.security import UserContext
from app.exceptions import ExternalDependencyError
from app.schemas.v0.payments_schemas import (
    ConfirmarRetornoRequest,
    OrdenEstadoResponse,
    PagosConfigResponse,
    PreferenciaCreate,
    PreferenciaResponse,
    WebhookMockTrigger,
)
from app.services.tiers import get_price, get_tier_strategy
from app.services.v0.reports.report_job_service import generar_informe_task

logger = logging.getLogger("payment_service")

_MP_STATUS_TO_ESTADO = {
    "approved": "approved",
    "authorized": "approved",
    "pending": "pending",
    "in_process": "pending",
    "in_mediation": "pending",
    "rejected": "rejected",
    "cancelled": "rejected",
    "refunded": "rejected",
    "charged_back": "rejected",
}


def obtener_config_pagos() -> PagosConfigResponse:
    base = (settings.PUBLIC_APP_URL or "").strip().rstrip("/")
    return PagosConfigResponse(
        payments_mock=settings.PAYMENTS_MOCK,
        checkout_pro=not settings.PAYMENTS_MOCK,
        sandbox=not settings.PAYMENTS_MOCK and settings.MERCADOPAGO_SANDBOX,
        sandbox_buyer_configured=False,
        public_key=settings.MERCADOPAGO_PUBLIC_KEY or None,
        public_return_url_configured=checkout_return_base_valid(base) if base else False,
    )


def orden_estado_response(orden: OrdenPago) -> OrdenEstadoResponse:
    return OrdenEstadoResponse(
        orden_id=orden.id,
        estado_pago=orden.estado_pago,
        reporte_listo=bool(orden.resultado_json and orden.foda_json),
        tier_adquirido=orden.tier_adquirido,
    )


def _assert_orden_accesible(orden: OrdenPago, user: UserContext) -> None:
    if orden.cognito_user_id != user.cognito_user_id and "admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes autorización para consultar esta orden.",
        )


def _procesar_pago_aprobado(
    orden: OrdenPago,
    db: Session,
    background_tasks: BackgroundTasks,
) -> dict:
    if orden.estado_pago == "approved":
        logger.info("Webhook ignorado: Orden %s ya estaba aprobada.", orden.id)
        return {"status": "ignored", "detail": "Order already processed.", "orden_id": orden.id}

    orden.estado_pago = "approved"
    db.commit()
    background_tasks.add_task(generar_informe_task, orden.id)
    logger.info("Pago acreditado para Orden ID %s. BackgroundTask lanzada.", orden.id)
    return {
        "status": "processing",
        "detail": "Payment accepted. Processing report in background.",
        "orden_id": orden.id,
    }


def aplicar_estado_mp(
    orden: OrdenPago,
    mp_status: str,
    db: Session,
    background_tasks: BackgroundTasks,
) -> dict:
    estado = _MP_STATUS_TO_ESTADO.get(mp_status, "pending")
    if estado == "approved":
        return _procesar_pago_aprobado(orden, db, background_tasks)

    if orden.estado_pago != estado:
        orden.estado_pago = estado
        db.commit()
    return {"status": "received", "detail": f"Payment status updated to {estado}.", "orden_id": orden.id}


def crear_preferencia_cobro(
    payload: PreferenciaCreate,
    db: Session,
    user: UserContext,
) -> PreferenciaResponse:
    # Tier y monto siempre desde registry/estrategia (servidor), no desde un precio del cliente.
    strategy = get_tier_strategy(payload.tier_adquirido)
    tier_id = strategy.tier_id
    monto = get_price(tier_id)

    logger.info(
        "Creando preferencia de cobro para el usuario %s en el Tier: %s (monto servidor=%.2f)",
        user.cognito_user_id,
        tier_id,
        monto,
    )

    checkout_id = f"chk_{uuid.uuid4().hex[:12]}"

    modo_aliados = payload.modo_analisis_aliados
    config_guiada = payload.config_aliados_guiados
    aliados_sel = payload.aliados_seleccionados
    if not strategy.uses_aliados_guiados():
        modo_aliados = "automatico"
        config_guiada = None
        if not strategy.details().get("max_allies"):
            aliados_sel = None

    try:
        aliados_guardar = (
            config_guiada.atractores_confirmados if modo_aliados == "guiado" and config_guiada else aliados_sel
        )
        nueva_orden = OrdenPago(
            cognito_user_id=user.cognito_user_id,
            email=user.email,
            checkout_id=checkout_id,
            monto=monto,
            estado_pago="pending",
            tier_adquirido=tier_id,
            latitud=payload.latitud,
            longitud=payload.longitud,
            radio_metros=payload.radio_metros,
            rubro=payload.rubro,
            competidores_seleccionados=json.dumps(payload.competidores_seleccionados)
            if payload.competidores_seleccionados
            else None,
            aliados_seleccionados=json.dumps(aliados_guardar) if aliados_guardar else None,
            competidores_adicionales=payload.competidores_adicionales,
            aliados_adicionales=payload.aliados_adicionales if strategy.details().get("max_allies") else None,
            modo_analisis_aliados=modo_aliados,
            config_aliados_guiados=json.dumps(config_guiada.model_dump()) if config_guiada else None,
        )
        db.add(nueva_orden)
        db.commit()
        db.refresh(nueva_orden)

        if settings.PAYMENTS_MOCK:
            init_point = f"https://www.mercadopago.com.mx/checkout/v1/redirect?pref_id=mock_{checkout_id}"
            logger.info("Pagos MOCK: enlace simulado creado para checkout %s", checkout_id)
        else:
            try:
                init_point = crear_preferencia_checkout(
                    checkout_id=checkout_id,
                    monto=monto,
                    tier=tier_id,
                    payer_email=user.email or None,
                    orden_id=nueva_orden.id,
                )
            except ExternalDependencyError:
                raise
            except Exception as e:
                logger.error("Falla al conectar con la API de Mercado Pago: %s", e)
                raise ExternalDependencyError(
                    "No pudimos enlazar con la pasarela de pagos segura temporalmente.",
                    suggested_action="Intenta de nuevo en unos minutos.",
                ) from e

        logger.info("Orden pendiente guardada con ID: %s", nueva_orden.id)
        return PreferenciaResponse(
            orden_id=nueva_orden.id,
            checkout_id=checkout_id,
            monto=float(monto),
            estado_pago="pending",
            init_point=init_point,
        )
    except ExternalDependencyError:
        db.rollback()
        raise
    except HTTPException:
        db.rollback()
        raise
    except Exception as db_err:
        db.rollback()
        logger.error("Falla al guardar orden en BD: %s", db_err)
        raise db_err


def consultar_estado_orden(orden_id: int, db: Session, user: UserContext) -> OrdenEstadoResponse:
    orden = db.query(OrdenPago).filter(OrdenPago.id == orden_id).first()
    if not orden:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada.")
    _assert_orden_accesible(orden, user)
    return orden_estado_response(orden)


def confirmar_retorno_mercado_pago(
    payload: ConfirmarRetornoRequest,
    background_tasks: BackgroundTasks,
    db: Session,
    user: UserContext,
) -> OrdenEstadoResponse:
    orden = db.query(OrdenPago).filter(OrdenPago.id == payload.orden_id).first()
    if not orden:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada.")
    _assert_orden_accesible(orden, user)

    if orden.estado_pago == "approved":
        return orden_estado_response(orden)

    if not payload.payment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Falta payment_id para confirmar el pago con Mercado Pago.",
        )

    payment = obtener_pago(payload.payment_id)
    mp_status = payment.get("status") or "pending"
    ext_ref = payment.get("external_reference")
    if ext_ref and ext_ref != orden.checkout_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La referencia del pago no coincide con esta orden.",
        )
    if payload.external_reference and payload.external_reference != orden.checkout_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="external_reference no coincide con la orden.",
        )

    db.refresh(orden)
    result = aplicar_estado_mp(orden, mp_status, db, background_tasks)
    db.refresh(orden)
    logger.info(
        "Retorno MP confirmado orden=%s payment_id=%s status=%s result=%s",
        orden.id,
        payload.payment_id,
        mp_status,
        result.get("status"),
    )
    return orden_estado_response(orden)


def consultar_ultima_orden_aprobada(db: Session, user: UserContext) -> OrdenEstadoResponse:
    orden = (
        db.query(OrdenPago)
        .filter(
            OrdenPago.cognito_user_id == user.cognito_user_id,
            OrdenPago.estado_pago == "approved",
        )
        .order_by(OrdenPago.id.desc())
        .first()
    )
    if not orden:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay compras aprobadas asociadas a tu cuenta.",
        )
    return orden_estado_response(orden)


async def extraer_payment_id_desde_webhook(request) -> int | None:
    """Delega el parseo del webhook al client MercadoPago processed."""
    return await extraer_payment_id_webhook(request)


def procesar_webhook_mp(
    payment_id: int,
    db: Session,
    background_tasks: BackgroundTasks,
) -> dict:
    payment = obtener_pago(payment_id)
    checkout_id = payment.get("external_reference")
    mp_status = payment.get("status") or "pending"
    logger.info(
        "Webhook MP payment_id=%s status=%s external_reference=%s",
        payment_id,
        mp_status,
        checkout_id,
    )

    if not checkout_id:
        return {"status": "received", "detail": "Payment without external_reference."}

    orden = db.query(OrdenPago).filter(OrdenPago.checkout_id == checkout_id).first()
    if not orden:
        logger.warning("Webhook MP: orden no encontrada para checkout_id=%s", checkout_id)
        return {"status": "received", "detail": "Order not found for external_reference."}

    # Normalizar tier y validar monto contra el catálogo del servidor.
    strategy = get_tier_strategy(orden.tier_adquirido)
    if orden.tier_adquirido != strategy.tier_id:
        logger.warning(
            "Webhook MP: tier normalizado orden %s: %r -> %s",
            orden.id,
            orden.tier_adquirido,
            strategy.tier_id,
        )
        orden.tier_adquirido = strategy.tier_id

    expected = float(get_price(strategy.tier_id))
    transaction_amount = payment.get("transaction_amount")
    if transaction_amount is not None and mp_status in ("approved", "authorized"):
        paid = float(transaction_amount)
        if abs(paid - expected) > 0.01 and abs(paid - float(orden.monto or 0)) > 0.01:
            logger.error(
                "Webhook MP: monto inconsistente orden %s (pagado=%.2f, esperado=%.2f, orden=%.2f)",
                orden.id,
                paid,
                expected,
                float(orden.monto or 0),
            )
            return {
                "status": "rejected",
                "detail": "El monto acreditado no coincide con el plan contratado.",
                "orden_id": orden.id,
            }

    return aplicar_estado_mp(orden, mp_status, db, background_tasks)


def disparar_webhook_simulado(
    payload: WebhookMockTrigger,
    background_tasks: BackgroundTasks,
    db: Session,
    user: UserContext,
) -> dict:
    if not settings.PAYMENTS_MOCK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este endpoint de pruebas no está disponible en este entorno.",
        )

    orden = db.query(OrdenPago).filter(OrdenPago.checkout_id == payload.checkout_id).first()
    if not orden:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró ninguna orden con el checkout indicado.",
        )

    _assert_orden_accesible(orden, user)

    if orden.estado_pago == "approved":
        return {"status": "already_approved", "orden_id": orden.id, "detail": "La orden ya estaba aprobada."}

    if payload.estado_pago.lower() == "approved":
        logger.info("[WEBHOOK MOCK] Aprobación forzada para Orden ID: %s. Lanzando tarea asíncrona...", orden.id)
        orden.estado_pago = "approved"
        db.commit()
        background_tasks.add_task(generar_informe_task, orden.id)
        return {
            "status": "success",
            "orden_id": orden.id,
            "detail": "Acreditación simulada. Tarea en background detonada.",
        }

    orden.estado_pago = payload.estado_pago
    db.commit()
    return {
        "status": "success",
        "orden_id": orden.id,
        "detail": f"Estado de la orden actualizado a: {payload.estado_pago}",
    }
