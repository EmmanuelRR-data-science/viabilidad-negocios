import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
async def obtener_vista_previa_gratuita(
    lat: float,
    lng: float,
    radio_metros: int,
    rubro: str,
    request: Request,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """
    Vista Previa Gratuita: Retorna conteos e indicadores agregados básicos del INEGI
    y competencia en la zona de forma gratuita. Bloquea el listado detallado de competidores,
    análisis de afluencia BestTime y el razonamiento estratégico FODA del LLM (Bedrock).
    Acepta opcionalmente un body JSON con las selecciones de competidores/aliados del formulario
    para que la clasificación por IA funcione también en la vista previa.
    """
    logger.info(f"Generando Vista Previa Gratuita para usuario {user.cognito_user_id}")

    # Extraer selecciones opcionales del body JSON (si el frontend las envía)
    competidores_sel = None
    aliados_sel = None
    try:
        body = await request.json()
        competidores_sel = body.get("competidores_seleccionados")
        aliados_sel = body.get("aliados_seleccionados")
        logger.info(f"Selecciones recibidas en vista previa — Competidores: {competidores_sel} | Aliados: {aliados_sel}")
    except Exception:
        # No hay body o no es JSON válido — proceder con defaults
        pass

    try:
        # Procesar cálculos analíticos completos bajo el tier premium para habilitar gráficos en vista previa
        resultado = procesar_calculo_analitico(
            db, lat, lng, radio_metros, rubro, tier="premium",
            competidores_seleccionados=competidores_sel,
            aliados_seleccionados=aliados_sel,
        )

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
            # Enviamos listados completos para que el frontend los dibuje con blur
            "competidores_listado": resultado["competidores_listado"],
            "aliados_listado": resultado["aliados_listado"],
            "aliados_conteos": resultado["aliados_conteos"],
            "afluencia_peatonal": resultado["afluencia_peatonal"],
            "mensaje_tier": "¡Estás viendo la vista previa gratuita! Compra el reporte Básico o Pro para desbloquear mapas detallados de competencia, o Premium para afluencia y diagnóstico estratégico inteligente con IA.",
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
        import json

        # Comprobar si existe caché en la base de datos
        if orden.resultado_json and orden.foda_json:
            logger.info(f"Cargando reporte de orden {orden_id} desde el caché de base de datos.")
            analisis_cuant = json.loads(orden.resultado_json)
            foda_inteligente = json.loads(orden.foda_json)
        else:
            logger.info(f"Reporte de orden {orden_id} no precalculado. Calculando en tiempo real...")
            # 1. Obtener dirección física exacta
            direccion_res = obtener_direccion(float(orden.latitud), float(orden.longitud))

            # 2. Ejecutar cálculos analíticos según el Tier adquirido
            competidores_sel = (
                json.loads(orden.competidores_seleccionados) if orden.competidores_seleccionados else None
            )
            aliados_sel = json.loads(orden.aliados_seleccionados) if orden.aliados_seleccionados else None

            analisis_cuant = procesar_calculo_analitico(
                db=db,
                lat=float(orden.latitud),
                lng=float(orden.longitud),
                radio=orden.radio_metros,
                rubro=orden.rubro,
                tier=orden.tier_adquirido,
                competidores_seleccionados=competidores_sel,
                aliados_seleccionados=aliados_sel,
                competidores_adicionales=orden.competidores_adicionales,
                aliados_adicionales=orden.aliados_adicionales,
            )

            # Inyectar dirección física y contexto personalizado
            analisis_cuant["direccion"] = direccion_res["formato_completo"]
            analisis_cuant["competidores_adicionales"] = orden.competidores_adicionales
            analisis_cuant["aliados_adicionales"] = orden.aliados_adicionales

            # 3. Invocar Bedrock (Meta Llama 3) para diagnóstico FODA inteligente (Disponible en todos los Tiers de pago)
            foda_inteligente = generar_analisis_foda(analisis_cuant, orden.intenciones)

            # Guardar en base de datos para futuras peticiones
            orden.resultado_json = json.dumps(analisis_cuant, default=str)
            orden.foda_json = json.dumps(foda_inteligente, default=str)
            db.commit()

        # Los campos se calculan y envían siempre; el frontend controlará si se muestran nítidos o con blur según el Tier.

        return {
            "status": "success",
            "orden": {
                "id": orden.id,
                "checkout_id": orden.checkout_id,
                "tier": orden.tier_adquirido,
                "monto": float(orden.monto),
                "fecha_aprobacion": orden.fecha_aprobacion,
                "competidores_adicionales": orden.competidores_adicionales,
                "aliados_adicionales": orden.aliados_adicionales,
            },
            "metricas": analisis_cuant,
            "analisis_estrategico_ia": foda_inteligente,
        }

    except Exception as e:
        logger.error(f"Falla al generar reporte de orden {orden_id}: {e}")
        raise e


@router.get("/pdf/{orden_id}", status_code=status.HTTP_200_OK)
def obtener_url_descarga_pdf(
    request: Request,
    orden_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
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
            # Modo Desarrollo: Retornamos el link local que expone la descarga directa
            logger.info("[ROUTES] Modo Desarrollo: Retornando URL de descarga directa local.")
            base = str(request.base_url).rstrip("/")
            url_descarga = f"{base}/api/analizar/pdf/{orden.id}/descargar"
        else:
            # Modo Producción: Generar URL firmada real de Amazon S3
            import re

            import boto3

            rubro_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", orden.rubro.lower()).strip("_")
            filename = f"Reporte_Viabilidad_{rubro_slug}.pdf"

            s3_client = boto3.client("s3", region_name=AWS_REGION)
            url_descarga = s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": S3_REPORTS_BUCKET,
                    "Key": orden.s3_key_reporte,
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                },
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


@router.get("/pdf/{orden_id}/descargar", status_code=status.HTTP_200_OK)
def descargar_pdf_archivo(orden_id: int, db: Session = Depends(get_db)):
    """
    Descarga directamente el archivo PDF local en modo desarrollo para pruebas,
    configurando el encabezado Content-Disposition correcto.
    """
    import os
    import re

    from fastapi.responses import FileResponse

    if not DEV_MODE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La descarga directa local solo está disponible en modo desarrollo.",
        )

    orden = db.query(OrdenPago).filter(OrdenPago.id == orden_id).first()
    if not orden:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La orden solicitada no existe.")

    # Validar acreditación de pago
    if orden.estado_pago != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El análisis correspondiente no ha sido aprobado ni pagado.",
        )

    rubro_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", orden.rubro.lower()).strip("_")
    local_pdf_path = f"scratch/reports/{orden.checkout_id}_reporte_{rubro_slug}.pdf"

    if not os.path.exists(local_pdf_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo PDF del reporte no se encuentra disponible localmente.",
        )

    filename = f"Reporte_Viabilidad_{rubro_slug}.pdf"
    return FileResponse(path=local_pdf_path, filename=filename, media_type="application/pdf")


@router.get("/buscar-direccion", status_code=status.HTTP_200_OK)
def buscar_direccion(direccion: str, user: UserContext = Depends(get_current_user)):
    """
    Busca ubicaciones posibles (direcciones) y coordenadas asociadas
    a partir de una consulta en texto libre (Geocodificación Directa).
    """
    direccion_query = direccion.strip() if direccion else ""
    if not direccion_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="La dirección o palabra de búsqueda no puede estar vacía."
        )

    try:
        from app.google_places import buscar_coordenadas_por_direccion

        resultados = buscar_coordenadas_por_direccion(direccion_query)
        return {"status": "success", "resultados": resultados}
    except Exception as e:
        logger.error(f"Falla al geocodificar dirección '{direccion_query}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falla de comunicación con el servicio de geocodificación de Google.",
        ) from e
