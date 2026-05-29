import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.analytics import procesar_calculo_analitico
from app.auth import UserContext, get_current_user
from app.bedrock import generar_analisis_foda
from app.config import AWS_REGION, DEV_MODE, S3_REPORTS_BUCKET
from app.database import get_db
from app.google_places import obtener_direccion
from app.models import OrdenPago

logger = logging.getLogger("routes_analytics")

router = APIRouter(prefix="/api/analizar", tags=["Motor Analítico e INEGI"])


@router.get("/geocodificar", status_code=status.HTTP_200_OK)
def geocodificar_coordenadas(lat: float, lng: float, user: UserContext = Depends(get_current_user)):
    """
    Geocodificación Inversa: Convierte una latitud y longitud en una dirección
    estructurada mexicana (calle, número, colonia, código postal, municipio, estado, país).
    Útil para mostrar el banner de ubicación al hacer clic en el mapa.
    """
    logger.info(f"Petición de geocodificación para ({lat}, {lng}) por usuario {user.cognito_user_id}")
    try:
        direccion_res = obtener_direccion(lat, lng)
        return {"status": "success", "coordenadas": {"lat": lat, "lng": lng}, "direccion": direccion_res}
    except Exception as e:
        logger.error(f"Falla en geocodificador: {e}")
        raise e


@router.post("/previa", status_code=status.HTTP_200_OK)
def obtener_vista_previa_gratuita(
    lat: float,
    lng: float,
    radio_metros: int,
    rubro: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """
    Vista Previa Gratuita: Retorna conteos e indicadores agregados básicos del INEGI
    y competencia en la zona de forma gratuita. Bloquea el listado detallado de competidores,
    análisis de afluencia BestTime y el razonamiento estratégico FODA del LLM (Bedrock).
    """
    logger.info(f"Generando Vista Previa Gratuita para usuario {user.cognito_user_id}")
    try:
        # Procesar cálculos básicos bajo el tier gratuito / basico
        resultado = procesar_calculo_analitico(db, lat, lng, radio_metros, rubro, tier="basico")

        # Filtramos la respuesta para cumplir estrictamente con los límites de la Vista Previa (RF-05.4)
        return {
            "status": "success",
            "coordenadas": {"lat": lat, "lng": lng},
            "radio_metros": radio_metros,
            "rubro": rubro,
            "tier": "gratuito",
            "poblacion_estimada": resultado["poblacion_ponderada"],
            "competidores_conteo": resultado["competidores_conteo"],
            "score_viabilidad_sva": resultado["sva"],
            "direccion": obtener_direccion(lat, lng)["formato_completo"],
            # Bloqueamos listados individuales y análisis avanzados en el Tier gratuito
            "competidores_listado": [],
            "afluencia_peatonal": {},
            "mensaje_tier": "¡Estás viendo la vista previa gratuita! Compra el reporte Básico o Pro para desbloquear mapas detallados de competencia, o Premium para afluencia y diagnóstico estratégico IA (Bedrock).",
        }
    except Exception as e:
        logger.error(f"Falla en cálculo de vista previa: {e}")
        raise e


@router.get("/resultado/{orden_id}", status_code=status.HTTP_200_OK)
def obtener_resultado_analisis(
    orden_id: int, db: Session = Depends(get_db), user: UserContext = Depends(get_current_user)
):
    """
    Desbloquea e integra el reporte cuantitativo (INEGI, Places, BestTime) e inteligente (AWS Bedrock)
    una vez que la orden ha sido pagada ('approved'). Controla estrictamente los accesos por Tiers.
    """
    logger.info(f"Cargando reporte de orden {orden_id} solicitado por usuario {user.cognito_user_id}")

    orden = db.query(OrdenPago).filter(OrdenPago.id == orden_id).first()
    if not orden:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="La orden de análisis comercial solicitada no existe."
        )

    # Validar propiedad o rol de administrador
    if orden.cognito_user_id != user.cognito_user_id and "admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes autorización para acceder a este reporte comercial.",
        )

    # Validar acreditación de pago
    if orden.estado_pago != "approved":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="El análisis está pendiente de pago. Por favor acredita el pago en Mercado Pago.",
        )

    try:
        # 1. Obtener dirección física exacta
        direccion_res = obtener_direccion(float(orden.latitud), float(orden.longitud))

        # 2. Ejecutar cálculos analíticos según el Tier adquirido
        analisis_cuant = procesar_calculo_analitico(
            db, float(orden.latitud), float(orden.longitud), orden.radio_metros, orden.rubro, tier=orden.tier_adquirido
        )

        # Inyectar dirección física
        analisis_cuant["direccion"] = direccion_res["formato_completo"]

        # 3. Invocar Bedrock (Meta Llama 3) para diagnóstico FODA inteligente (Disponible en todos los Tiers de pago)
        foda_inteligente = generar_analisis_foda(analisis_cuant, orden.intenciones)

        # 4. Ajustar y omitir campos en base al Tier adquirido para respetar los privilegios (RF-05.4)
        if orden.tier_adquirido == "basico":
            # Básico no muestra mapa de competidores individuales ni afluencia
            analisis_cuant["competidores_listado"] = []
            analisis_cuant["afluencia_peatonal"] = {}
        elif orden.tier_adquirido == "pro":
            # Pro muestra competidores pero no afluencia peatonal BestTime
            analisis_cuant["afluencia_peatonal"] = {}

        return {
            "status": "success",
            "orden": {
                "id": orden.id,
                "checkout_id": orden.checkout_id,
                "tier": orden.tier_adquirido,
                "monto": float(orden.monto),
                "fecha_aprobacion": orden.fecha_aprobacion,
            },
            "metricas": analisis_cuant,
            "analisis_estrategico_ia": foda_inteligente,
        }

    except Exception as e:
        logger.error(f"Falla al generar reporte de orden {orden_id}: {e}")
        raise e


@router.get("/pdf/{orden_id}", status_code=status.HTTP_200_OK)
def obtener_url_descarga_pdf(
    orden_id: int, db: Session = Depends(get_db), user: UserContext = Depends(get_current_user)
):
    """
    Genera una URL firmada de descarga segura (Presigned URL) de 10 minutos
    para descargar el reporte en PDF privado almacenado en Amazon S3.
    Valida los accesos a través del token Cognito JWT.
    """
    logger.info(f"Petición de descarga de PDF para la orden {orden_id} por el usuario {user.cognito_user_id}")

    orden = db.query(OrdenPago).filter(OrdenPago.id == orden_id).first()
    if not orden:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La orden solicitada no existe.")

    # Validar propiedad o rol de administrador
    if orden.cognito_user_id != user.cognito_user_id and "admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes autorización para descargar este reporte comercial.",
        )

    # Validar acreditación de pago
    if orden.estado_pago != "approved":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="El análisis está pendiente de pago o procesamiento."
        )

    if not orden.s3_key_reporte:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El reporte PDF aún se encuentra en proceso de compilación en segundo plano. Por favor, recarga en unos segundos.",
        )

    try:
        if DEV_MODE:
            # Modo Desarrollo: Retornamos el link local que FastAPI sirve estáticamente
            logger.info("[ROUTES] Modo Desarrollo: Retornando URL de descarga de servidor estático local.")
            url_descarga = f"http://localhost:8000/static/reports/{orden.checkout_id}_reporte.pdf"
        else:
            # Modo Producción: Generar URL firmada real de Amazon S3
            import boto3

            s3_client = boto3.client("s3", region_name=AWS_REGION)
            url_descarga = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": S3_REPORTS_BUCKET, "Key": orden.s3_key_reporte},
                ExpiresIn=600,  # 10 minutos (600 segundos)
            )
            logger.info("[ROUTES] URL firmada de S3 generada exitosamente.")

        return {
            "status": "success",
            "orden_id": orden.id,
            "checkout_id": orden.checkout_id,
            "url_descarga": url_descarga,
            "validez_segundos": 600,
            "mensaje_seguridad": "Este enlace es privado y tiene una vigencia limitada de 10 minutos por ciberseguridad corporativa.",
        }

    except Exception as e:
        logger.error(f"Error al generar presigned URL: {e}")
        raise e
