import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.orm import Session

from app.clients.v0.database import get_db
from app.core.config import PAYMENTS_MOCK
from app.core.security import UserContext, get_current_user
from app.exceptions import ExternalDependencyError
from app.schemas.v0.payments_schemas import (
    ConfirmarRetornoRequest,
    OrdenEstadoResponse,
    PagosConfigResponse,
    PreferenciaCreate,
    PreferenciaResponse,
    WebhookMockTrigger,
)
from app.services.v0.payments import payment_service

logger = logging.getLogger("payments_router")

router = APIRouter(prefix="/api/pagos", tags=["Transacciones y Pagos"])


@router.get("/config", response_model=PagosConfigResponse)
def obtener_config_pagos():
    return payment_service.obtener_config_pagos()


@router.post("/preferencia", response_model=PreferenciaResponse, status_code=status.HTTP_201_CREATED)
def crear_preferencia_cobro(
    payload: PreferenciaCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    return payment_service.crear_preferencia_cobro(payload, db, user)


@router.get("/orden/{orden_id}/estado", response_model=OrdenEstadoResponse)
def consultar_estado_orden(
    orden_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    return payment_service.consultar_estado_orden(orden_id, db, user)


@router.post("/confirmar-retorno", response_model=OrdenEstadoResponse)
def confirmar_retorno_mercado_pago(
    payload: ConfirmarRetornoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    return payment_service.confirmar_retorno_mercado_pago(payload, background_tasks, db, user)


@router.get("/mi-ultima-aprobada", response_model=OrdenEstadoResponse)
def consultar_ultima_orden_aprobada(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    return payment_service.consultar_ultima_orden_aprobada(db, user)


@router.api_route("/webhook", methods=["GET", "POST"])
async def recibir_notificacion_pago(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if PAYMENTS_MOCK:
        return {"status": "ignored", "detail": "Webhook live disabled while PAYMENTS_MOCK is active."}

    payment_id = await payment_service.extraer_payment_id_desde_webhook(request)
    if not payment_id:
        logger.info("Webhook MP recibido sin payment_id procesable (orden abierta o pago aún no creado).")
        return {"status": "received", "detail": "Notification received without payment id."}

    try:
        return payment_service.procesar_webhook_mp(payment_id, db, background_tasks)
    except ExternalDependencyError as exc:
        logger.warning("Webhook MP: pago %s no listo aún (%s)", payment_id, exc.message)
        return {"status": "received", "detail": "Payment not ready yet."}
    except Exception as err:
        logger.error("Error consultando pago %s en MP: %s", payment_id, err)
        raise ExternalDependencyError(
            "No se pudo validar el pago con Mercado Pago.",
            suggested_action="El webhook se reintentará automáticamente.",
        ) from err


@router.post("/webhook-mock")
def disparar_webhook_simulado(
    payload: WebhookMockTrigger,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return payment_service.disparar_webhook_simulado(payload, background_tasks, db)
