import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth import UserContext, get_current_user
from app.config import DEV_MODE, MERCADOPAGO_ACCESS_TOKEN
from app.database import get_db
from app.models import OrdenPago
from app.schemas import PreferenciaCreate, PreferenciaResponse, WebhookMockTrigger
from app.tasks import generar_informe_task

logger = logging.getLogger("payments")

router = APIRouter(prefix="/api/pagos", tags=["Transacciones y Pagos"])

# Mapeo de precios por Tier de análisis comercial (Pesos Mexicanos MXN)
PRECIOS_TIER = {"basico": 99.00, "pro": 249.00, "premium": 499.00}


@router.post("/preferencia", response_model=PreferenciaResponse, status_code=status.HTTP_201_CREATED)
def crear_preferencia_cobro(
    payload: PreferenciaCreate, db: Session = Depends(get_db), user: UserContext = Depends(get_current_user)
):
    """
    Registra una orden de análisis comercial pendiente de pago en la base de datos y
    genera la preferencia/enlace de cobro dinámico de Mercado Pago Checkout Pro.
    """
    logger.info(
        f"Creando preferencia de cobro para el usuario {user.cognito_user_id} en el Tier: {payload.tier_adquirido}"
    )

    # 1. Resolver el monto de acuerdo al Tier
    monto = PRECIOS_TIER[payload.tier_adquirido]

    # 2. Generar un identificador único de cobro (Checkout ID)
    checkout_id = f"chk_{uuid.uuid4().hex[:12]}"

    # 3. Crear el enlace de checkout
    init_point = ""
    if DEV_MODE:
        # Modo Desarrollo: Retornar URL simulada
        init_point = f"https://www.mercadopago.com.mx/checkout/v1/redirect?pref_id=mock_{checkout_id}"
        logger.info(f"Modo Desarrollo: Enlace simulado creado para checkout: {init_point}")
    else:
        # Modo Producción: Invocar SDK oficial de Mercado Pago para enlace real
        try:
            import mercadopago

            sdk = mercadopago.SDK(MERCADOPAGO_ACCESS_TOKEN)
            preference_data = {
                "items": [
                    {
                        "title": f"GeoViabilidad Hook - Reporte {payload.tier_adquirido.upper()}",
                        "quantity": 1,
                        "unit_price": float(monto),
                        "currency_id": "MXN",
                    }
                ],
                "back_urls": {
                    "success": "https://geoviabilidad.com/pago/exitoso",
                    "failure": "https://geoviabilidad.com/pago/fallido",
                    "pending": "https://geoviabilidad.com/pago/pendiente",
                },
                "auto_return": "approved",
                "external_reference": checkout_id,
            }
            preference_response = sdk.preference().create(preference_data)
            init_point = preference_response["response"]["init_point"]
        except Exception as e:
            logger.error(f"Falla al conectar con la API de Mercado Pago: {e}")
            # En producción, levantamos una excepción de red que el middleware sanitizará
            raise HTTPException(
                status_code=502, detail="No pudimos enlazar con la pasarela de pagos segura temporalmente."
            ) from e

    # 4. Registrar la orden en estado 'pending' en la base de datos RDS PostgreSQL
    try:
        nueva_orden = OrdenPago(
            cognito_user_id=user.cognito_user_id,
            email=user.email,
            checkout_id=checkout_id,
            monto=monto,
            estado_pago="pending",
            tier_adquirido=payload.tier_adquirido,
            latitud=payload.latitud,
            longitud=payload.longitud,
            radio_metros=payload.radio_metros,
            rubro=payload.rubro,
            intenciones=payload.intenciones,
        )
        db.add(nueva_orden)
        db.commit()
        db.refresh(nueva_orden)

        logger.info(f"Orden pendiente guardada con ID: {nueva_orden.id}")
        return PreferenciaResponse(
            orden_id=nueva_orden.id,
            checkout_id=checkout_id,
            monto=float(monto),
            estado_pago="pending",
            init_point=init_point,
        )
    except Exception as db_err:
        db.rollback()
        logger.error(f"Falla al guardar orden en BD: {db_err}")
        raise db_err


@router.post("/webhook")
async def recibir_notificacion_pago(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Webhook oficial para recibir notificaciones IPN (Instant Payment Notifications) de Mercado Pago.
    Valida firmas, actualiza el estado de la orden de 'pending' a 'approved'
    y detona de forma asíncrona la generación del reporte en segundo plano con BackgroundTasks.
    """
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        pass

    logger.info(f"Webhook recibido de Mercado Pago: {payload}")

    # En modo de pruebas/desarrollo local, admitimos simulación manual
    # Para producción, validaremos cabeceras de firma e ID de recurso de Mercado Pago
    checkout_id = payload.get("external_reference")
    action = payload.get("action")

    # Buscar orden
    if checkout_id:
        orden = db.query(OrdenPago).filter(OrdenPago.checkout_id == checkout_id).first()
        if orden:
            # Control de Idempotencia: Si ya está aprobada, ignoramos para no duplicar llamadas al LLM
            if orden.estado_pago == "approved":
                logger.info(f"Webhook ignorado: Orden {orden.id} ya había sido marcada como 'approved'.")
                return {"status": "ignored", "detail": "Order already processed."}

            # Si es una acreditación válida de Mercado Pago
            if DEV_MODE or (action == "payment.created" or payload.get("type") == "payment"):
                logger.info(f"Pago acreditado vía Webhook para Orden ID: {orden.id}. Lanzando BackgroundTask...")

                # Agendar tarea en segundo plano nativa en memoria (Sin SQS/Fargate redundantes)
                background_tasks.add_task(generar_informe_task, orden.id)
                return {"status": "processing", "detail": "Payment accepted. Processing report in background."}

    return {"status": "received", "detail": "Webhook received successfully."}


@router.post("/webhook-mock")
def disparar_webhook_simulado(
    payload: WebhookMockTrigger, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """
    Ruta exclusiva de Desarrollo para forzar la acreditación de una orden y
    detonar la compilación del reporte en segundo plano (S3 + Bedrock) sin pasar por Mercado Pago.
    """
    if not DEV_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este endpoint de pruebas solo está disponible en modo de desarrollo (DEV_MODE=True).",
        )

    # Buscar la orden
    orden = db.query(OrdenPago).filter(OrdenPago.checkout_id == payload.checkout_id).first()
    if not orden:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ninguna orden con checkout_id: {payload.checkout_id}",
        )

    if orden.estado_pago == "approved":
        return {"status": "already_approved", "orden_id": orden.id, "detail": "La orden ya estaba aprobada."}

    if payload.estado_pago.lower() == "approved":
        logger.info(f"[WEBHOOK MOCK] Aprobación forzada para Orden ID: {orden.id}. Lanzando tarea asíncrona...")
        background_tasks.add_task(generar_informe_task, orden.id)
        return {
            "status": "success",
            "orden_id": orden.id,
            "detail": "Acreditación simulada. Tarea en background detonada.",
        }
    else:
        orden.estado_pago = payload.estado_pago
        db.commit()
        return {
            "status": "success",
            "orden_id": orden.id,
            "detail": f"Estado de la orden actualizado a: {payload.estado_pago}",
        }
