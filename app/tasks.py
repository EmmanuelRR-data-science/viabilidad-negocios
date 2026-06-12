import datetime
import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.orm import Session

from app.analytics import procesar_calculo_analitico
from app.config import AWS_REGION, DEV_MODE, S3_REPORTS_BUCKET, SES_SENDER_EMAIL
from app.database import SessionLocal
from app.models import OrdenPago
from app.reports import ReportLabGenerator

logger = logging.getLogger("tasks")


def generar_informe_task(orden_id: int):
    """
    Tarea en segundo plano de FastAPI que ejecuta la recopilación demográfica de PostGIS,
    invoca a Amazon Bedrock para generar el análisis FODA interactivo en base a las intenciones del usuario,
    compila el reporte PDF real con ReportLab y lo guarda de forma segura en Amazon S3.
    Finalmente, envía una confirmación con un enlace de descarga seguro al cliente vía Amazon SES.
    """
    logger.info(f"--- [TASK] Iniciando procesamiento asíncrono para Orden ID: {orden_id} ---")

    # Crear sesión de base de datos local aislada para el hilo de fondo
    db: Session = SessionLocal()
    try:
        # Obtener la orden de la base de datos
        orden = db.query(OrdenPago).filter(OrdenPago.id == orden_id).first()
        if not orden:
            logger.error(f"[TASK] Orden con ID {orden_id} no encontrada en la base de datos.")
            return

        # Deserializar listas de selección personalizadas
        import json

        competidores_sel = json.loads(orden.competidores_seleccionados) if orden.competidores_seleccionados else None
        aliados_sel = json.loads(orden.aliados_seleccionados) if orden.aliados_seleccionados else None
        config_guiada = json.loads(orden.config_aliados_guiados) if orden.config_aliados_guiados else None
        modo_aliados = getattr(orden, "modo_analisis_aliados", None) or "automatico"
        if modo_aliados == "guiado" and config_guiada:
            aliados_sel = config_guiada.get("atractores_confirmados")

        # 1. Ejecutar el cálculo analítico real geoespacial (PostGIS, Places, BestTime)
        logger.info(f"[TASK] Calculando analíticas para coordenadas: ({orden.latitud}, {orden.longitud})...")
        resultado = procesar_calculo_analitico(
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
            intenciones=orden.intenciones,
            modo_analisis_aliados=modo_aliados,
            config_aliados_guiados=config_guiada,
        )

        # Cálculo multi-radio REAL con PostGIS: población y densidad por anillo de cobertura.
        # Solo la población se re-consulta por radio; competidores/aliados se miden únicamente
        # en el radio contratado para no extrapolar datos.
        import math

        from app.analytics import obtener_demografia_ponderada

        radio_contratado_km = round(orden.radio_metros / 1000.0, 1)
        radios_km = sorted({radio_contratado_km, 3.0, 5.0})
        multi_radio = []
        for r_km in radios_km:
            if abs(r_km - radio_contratado_km) < 0.01:
                pob_r = resultado["poblacion_ponderada"]
            else:
                demog_r = obtener_demografia_ponderada(
                    db, float(orden.latitud), float(orden.longitud), int(r_km * 1000)
                )
                pob_r = demog_r["poblacion_ponderada"]
            area_r_km2 = math.pi * (r_km**2)
            multi_radio.append(
                {
                    "radio_km": r_km,
                    "es_radio_contratado": abs(r_km - radio_contratado_km) < 0.01,
                    "poblacion": pob_r,
                    "densidad": round(pob_r / area_r_km2, 1) if area_r_km2 > 0 else 0,
                }
            )
        resultado["multi_radio"] = multi_radio

        # Geocodificar la dirección física real para incluirla en el reporte PDF
        from app.google_places import obtener_direccion

        try:
            dir_res = obtener_direccion(float(orden.latitud), float(orden.longitud))
            resultado["direccion"] = dir_res["formato_completo"]
            resultado["localidad"] = dir_res["localidad"]
        except Exception as geocode_err:
            logger.error(f"[TASK] Error al geocodificar dirección para reporte: {geocode_err}")
            resultado["direccion"] = "Dirección física no resuelta en México"
            resultado["localidad"] = "México"

        resultado["competidores_adicionales"] = orden.competidores_adicionales
        resultado["aliados_adicionales"] = orden.aliados_adicionales

        # Obtener mapa estático de Google si estamos en PRO o PREMIUM
        resultado["map_bytes"] = None
        if orden.tier_adquirido in ["pro", "premium"]:
            logger.info("[TASK] Generando mapa de alta resolución para el PDF...")
            from app.google_places import obtener_mapa_estatico
            from app.map_image import generar_mapa_reporte

            es_premium = orden.tier_adquirido == "premium"
            map_bytes = generar_mapa_reporte(
                lat=float(orden.latitud),
                lng=float(orden.longitud),
                radio=orden.radio_metros,
                competidores=resultado.get("competidores_listado", []),
                aliados=resultado.get("aliados_listado", []),
                incluir_aliados=es_premium,
            )
            if not map_bytes:
                map_bytes = obtener_mapa_estatico(
                    lat=float(orden.latitud),
                    lng=float(orden.longitud),
                    radio=orden.radio_metros,
                    competidores=resultado.get("competidores_listado", []),
                    aliados=resultado.get("aliados_listado", []),
                    incluir_aliados=es_premium,
                )
            resultado["map_bytes"] = map_bytes

        poblacion_estimada = resultado["poblacion_ponderada"]
        competidores_conteo = resultado["competidores_conteo"]
        sva = resultado["sva"]

        # 2. Diagnóstico FODA: Groq en pruebas/producción; sin AWS en modo pruebas
        logger.info("[TASK] Generando diagnóstico estratégico (Groq o respaldo cuantitativo)...")
        from app.bedrock import _foda_respaldo_cuantitativo, generar_analisis_foda

        try:
            analysis_result = generar_analisis_foda(resultado, orden.intenciones)
            logger.info("[TASK] Diagnóstico estratégico generado exitosamente.")
        except Exception as foda_err:
            logger.error(f"[TASK] Error al generar diagnóstico estratégico: {foda_err}")
            analysis_result = _foda_respaldo_cuantitativo(
                resultado,
                orden.rubro,
                comp_adicionales=orden.competidores_adicionales,
                aliados_adicionales=orden.aliados_adicionales,
            )

        # 3. Compilar el PDF real con ReportLab
        logger.info("[TASK] Compilando reporte PDF ejecutivo real mediante ReportLab...")
        try:
            pdf_bytes = ReportLabGenerator.construir_reporte_pdf(orden, resultado, analysis_result)
            logger.info(f"[TASK] Compilación de PDF exitosa ({len(pdf_bytes)} bytes generados).")
        except Exception as pdf_err:
            logger.error(f"[TASK] Error crítico en compilador de PDF: {pdf_err}")
            raise pdf_err

        import re

        rubro_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", orden.rubro.lower()).strip("_")
        # Definir la clave S3 privada
        s3_key = f"informes/{orden.cognito_user_id}/{orden.checkout_id}_reporte_{rubro_slug}.pdf"

        # 4. Guardar Reporte en Amazon S3 (o disco local si DEV_MODE)
        if DEV_MODE:
            logger.info("[TASK] Modo Desarrollo: Guardando PDF localmente para inspección...")
            os.makedirs("scratch/reports", exist_ok=True)
            local_pdf_path = f"scratch/reports/{orden.checkout_id}_reporte_{rubro_slug}.pdf"
            with open(local_pdf_path, "wb") as f:
                f.write(pdf_bytes)
            logger.info(f"[TASK] PDF de desarrollo persistido en: {local_pdf_path}")

            # Simulamos presigned URL de descarga local
            presigned_url = f"http://localhost:8000/static/reports/{orden.checkout_id}_reporte_{rubro_slug}.pdf"
        else:
            # Modo Producción: Subir realmente el objeto a S3 con encriptación ServerSide KMS
            try:
                logger.info(f"[TASK] Guardando reporte PDF en S3: s3://{S3_REPORTS_BUCKET}/{s3_key}")
                s3_client = boto3.client("s3", region_name=AWS_REGION)
                s3_client.put_object(
                    Bucket=S3_REPORTS_BUCKET,
                    Key=s3_key,
                    Body=pdf_bytes,
                    ContentType="application/pdf",
                    ServerSideEncryption="aws:kms",  # Cifrado del lado del servidor SSE-KMS integrado
                )
                logger.info("[TASK] Archivo PDF guardado encriptado en S3 exitosamente.")

                # Generar presigned URL con validez de 24 horas para incrustar en el correo de SES
                presigned_url = s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": S3_REPORTS_BUCKET, "Key": s3_key},
                    ExpiresIn=86400,  # 24 horas
                )
            except (BotoCoreError, ClientError) as s3_err:
                logger.error(f"[TASK] Error al subir archivo a S3: {s3_err}")
                presigned_url = "https://geoviabilidad.com/reportes/descarga-directa"

        # 5. Actualizar estado de la orden a aprobado, guardar clave, guardar caché del reporte y registrar fecha
        logger.info("[TASK] Actualizando registro transaccional en base de datos con caché del reporte...")
        import json

        orden.estado_pago = "approved"
        orden.s3_key_reporte = s3_key
        foda_para_cache = {
            k: v for k, v in analysis_result.items() if k == "_fuente" or not str(k).startswith("_")
        }
        orden.resultado_json = json.dumps(resultado, default=str)
        orden.foda_json = json.dumps(foda_para_cache, default=str)
        orden.fecha_aprobacion = datetime.datetime.utcnow()
        db.commit()

        # 6. Envío de Correo mediante Amazon SES (o guardado local de .eml si DEV_MODE)
        subject = f"¡Tu Reporte de GeoViabilidad Hook para '{orden.rubro.capitalize()}' está listo!"

        # Determinar número de páginas según Tier
        paginas_tier = 6 if orden.tier_adquirido == "basico" else (10 if orden.tier_adquirido == "pro" else 13)

        # Cuerpo del correo en HTML Premium
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #334155; line-height: 1.6; margin: 0; padding: 0; background-color: #f8fafc; }}
                .container {{ max-width: 600px; margin: 30px auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
                .header {{ background-color: #0f172a; padding: 40px 30px; text-align: center; color: #ffffff; }}
                .header h1 {{ margin: 0; font-size: 24px; font-weight: bold; letter-spacing: 0.5px; }}
                .content {{ padding: 30px; }}
                .kpi-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                .kpi-table td {{ border: 1px solid #e2e8f0; padding: 12px; text-align: center; background-color: #f1f5f9; }}
                .kpi-val {{ font-size: 20px; font-weight: bold; color: #2563eb; }}
                .kpi-lbl {{ font-size: 10px; font-weight: bold; color: #64748b; text-transform: uppercase; }}
                .btn {{ display: inline-block; padding: 14px 28px; background-color: #2563eb; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-weight: bold; text-align: center; margin: 25px 0; }}
                .footer {{ background-color: #f1f5f9; padding: 20px; text-align: center; font-size: 11px; color: #64748b; border-top: 1px solid #e2e8f0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>GEOVIABILIDAD HOOK</h1>
                </div>
                <div class="content">
                    <p>Estimado/a cliente,</p>
                    <p>Nos complace notificarte que tu estudio de <b>Localización Inteligente y Geomarketing</b> ha sido procesado de forma exitosa.</p>
                    <p>Tu reporte ejecutivo en formato PDF de <b>{paginas_tier} páginas</b> ha sido compilado para el giro comercial <b>'{orden.rubro}'</b> en base a los datos demográficos espaciales de INEGI.</p>
                    
                    <table class="kpi-table">
                        <tr>
                            <td><span class="kpi-lbl">Score SVA</span><br/><span class="kpi-val">{sva}/100</span></td>
                            <td><span class="kpi-lbl">Población Residente</span><br/><span class="kpi-val">{poblacion_estimada:,} hab.</span></td>
                            <td><span class="kpi-lbl">Competidores</span><br/><span class="kpi-val">{competidores_conteo}</span></td>
                        </tr>
                    </table>

                    <p>Puedes descargar tu informe PDF encriptado de forma segura y directa haciendo clic en el siguiente botón. Este enlace tiene una <b>vigencia de 24 horas</b> por motivos de seguridad corporativa:</p>
                    
                    <div style="text-align: center;">
                        <a href="{presigned_url}" class="btn" target="_blank">DESCARGAR REPORTE PDF</a>
                    </div>
                    
                    <p>Si el enlace expira, siempre podrás ingresar al dashboard interactivo de la plataforma utilizando tu cuenta y generar un nuevo acceso.</p>
                    <p>Atentamente,<br/><b>El equipo de Data Science de GeoViabilidad Hook</b></p>
                </div>
                <div class="footer">
                    Este es un correo automático confidencial. Si recibiste este mensaje por error, por favor notifícanos de inmediato.
                </div>
            </div>
        </body>
        </html>
        """

        if DEV_MODE:
            logger.info("[TASK] Modo Desarrollo: Simulando envío de correo vía Amazon SES...")
            os.makedirs("scratch/emails", exist_ok=True)
            local_email_path = f"scratch/emails/email_orden_{orden.id}.html"
            with open(local_email_path, "w", encoding="utf-8") as f:
                f.write(html_body)
            logger.info(f"[TASK] HTML del correo guardado para visualización local en: {local_email_path}")
        else:
            try:
                logger.info(f"[TASK] Enviando correo SES real de {SES_SENDER_EMAIL} a {orden.email}...")
                ses_client = boto3.client("ses", region_name=AWS_REGION)
                ses_client.send_email(
                    Source=SES_SENDER_EMAIL,
                    Destination={"ToAddresses": [orden.email]},
                    Message={
                        "Subject": {"Data": subject, "Charset": "UTF-8"},
                        "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
                    },
                )
                logger.info("[TASK] Correo electrónico enviado vía Amazon SES exitosamente.")
            except (BotoCoreError, ClientError) as ses_err:
                logger.error(f"[TASK] Error al enviar correo por Amazon SES: {ses_err}")

        logger.info(f"[TASK] --- ¡INFORME COMPLETADO CON ÉXITO PARA LA ORDEN {orden.id}! ---")

    except Exception as e:
        logger.exception(f"[TASK] Error catastrófico en la tarea en segundo plano: {e}")
        db.rollback()
    finally:
        db.close()
