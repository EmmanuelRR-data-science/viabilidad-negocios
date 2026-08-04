import logging

from fastapi import APIRouter, BackgroundTasks, Request, status

from app.core.config import settings
from app.core.deps import DbDep, UserDep
from app.exceptions import ExternalDependencyError
from app.schemas.v0.payments_schemas import (
    ConfirmarRetornoRequest,
    OrdenEstadoResponse,
    PagosConfigResponse,
    PreferenciaCreate,
    PreferenciaResponse,
    WebhookAckResponse,
    WebhookMockTrigger,
)
from app.services.v0.payments import payment_service

logger = logging.getLogger("payments_router")


router = APIRouter(prefix="/api/pagos", tags=["Transacciones y Pagos"])


@router.get(
    "/config",
    response_model=PagosConfigResponse,
    summary="Configuración de pagos",
    description=(
        "Expone metadatos públicos del flujo de cobro para el frontend "
        "(modo checkout, sandbox, public key). No requiere auth."
    ),
)
def obtener_config_pagos():
    return payment_service.obtener_config_pagos()


@router.post(
    "/preferencia",
    response_model=PreferenciaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear preferencia / orden de cobro",
    description=(
        "Crea una orden pendiente para el punto (lat/lng), rubro y tier elegidos. "
        "Con pagos simulados devuelve un `init_point` simulado y un `checkout_id`.\n\n"
        "Requiere Bearer. Guarda `orden_id` y `checkout_id` para los pasos siguientes."
    ),
)
def crear_preferencia_cobro(
    payload: PreferenciaCreate,
    db: DbDep,
    user: UserDep,
):
    return payment_service.crear_preferencia_cobro(payload, db, user)


@router.get(
    "/orden/{orden_id}/estado",
    response_model=OrdenEstadoResponse,
    summary="Consultar estado de una orden",
    description=(
        "Devuelve `estado_pago` (`pending` / `approved` / …) y `reporte_listo`. "
        "Tras el webhook, haz poll hasta `reporte_listo=true` antes de pedir el PDF. "
        "Requiere Bearer."
    ),
)
def consultar_estado_orden(
    orden_id: int,
    db: DbDep,
    user: UserDep,
):
    return payment_service.consultar_estado_orden(orden_id, db, user)


@router.post(
    "/confirmar-retorno",
    response_model=OrdenEstadoResponse,
    summary="Confirmar retorno desde Checkout Pro",
    description=(
        "Endpoint usado cuando el comprador regresa del Checkout de Mercado Pago "
        "(flujo live/sandbox, no mock). Valida el retorno y puede disparar la generación "
        "del informe en background. Requiere Bearer."
    ),
)
def confirmar_retorno_mercado_pago(
    payload: ConfirmarRetornoRequest,
    background_tasks: BackgroundTasks,
    db: DbDep,
    user: UserDep,
):
    return payment_service.confirmar_retorno_mercado_pago(payload, background_tasks, db, user)


@router.get(
    "/mi-ultima-aprobada",
    response_model=OrdenEstadoResponse,
    summary="Última orden aprobada del usuario",
    description=(
        "Devuelve la orden aprobada más reciente del usuario autenticado "
        "(útil para reanudar descarga de PDF). Requiere Bearer."
    ),
)
def consultar_ultima_orden_aprobada(
    db: DbDep,
    user: UserDep,
):
    return payment_service.consultar_ultima_orden_aprobada(db, user)


@router.api_route(
    "/webhook",
    methods=["GET", "POST"],
    response_model=WebhookAckResponse,
    summary="Webhook Mercado Pago (live)",
    description=(
        "Recibe notificaciones IPN/webhooks de Mercado Pago en modo real/sandbox. "
        "Si el modo simulado está activo, responde un acuse genérico sin procesar.\n\n"
        "No requiere Bearer (lo llama Mercado Pago)."
    ),
)
async def recibir_notificacion_pago(
    request: Request,
    background_tasks: BackgroundTasks,
    db: DbDep,
):
    if settings.PAYMENTS_MOCK:
        return WebhookAckResponse(status="ignored", detail="Notificación recibida.")

    payment_id = await payment_service.extraer_payment_id_desde_webhook(request)

    if not payment_id:
        logger.info("Webhook MP recibido sin payment_id procesable (orden abierta o pago aún no creado).")

        return WebhookAckResponse(status="received", detail="Notification received without payment id.")

    try:
        result = payment_service.procesar_webhook_mp(payment_id, db, background_tasks)

        if isinstance(result, dict):
            return WebhookAckResponse(
                status=str(result.get("status", "received")),
                detail=result.get("detail"),
                orden_id=result.get("orden_id"),
            )

        return WebhookAckResponse(status="received")

    except ExternalDependencyError as exc:
        logger.warning("Webhook MP: pago %s no listo aún (%s)", payment_id, exc.message)

        return WebhookAckResponse(status="received", detail="Payment not ready yet.")

    except Exception as err:
        logger.error("Error consultando pago %s en MP: %s", payment_id, err)

        raise ExternalDependencyError(
            "No se pudo validar el pago con Mercado Pago.",
            suggested_action="El webhook se reintentará automáticamente.",
        ) from err


if settings.PAYMENTS_MOCK:

    @router.post(
        "/webhook-mock",
        response_model=WebhookAckResponse,
        summary="[MOCK] Aprobar pago simulado",
        description=(
            "**Solo con pagos simulados activos.** Marca una orden como `approved` usando su "
            "`checkout_id` y dispara en background el job de informe (análisis + PDF).\n\n"
            'Body: `{ "checkout_id": "chk_...", "estado_pago": "approved" }`.\n\n'
            "Requiere Bearer y ownership de la orden (o rol admin)."
        ),
    )
    def disparar_webhook_simulado(
        payload: WebhookMockTrigger,
        background_tasks: BackgroundTasks,
        db: DbDep,
        user: UserDep,
    ):
        return payment_service.disparar_webhook_simulado(payload, background_tasks, db, user)
