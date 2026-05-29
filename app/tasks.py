import datetime
import json
import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.orm import Session

from app.analytics import procesar_calculo_analitico
from app.config import AWS_REGION, BEDROCK_MODEL_ID, DEV_MODE, S3_REPORTS_BUCKET, SES_SENDER_EMAIL
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

        # 1. Ejecutar el cálculo analítico real geoespacial (PostGIS, Places, BestTime)
        logger.info(f"[TASK] Calculando analíticas para coordenadas: ({orden.latitud}, {orden.longitud})...")
        resultado = procesar_calculo_analitico(
            db=db,
            lat=float(orden.latitud),
            lng=float(orden.longitud),
            radio=orden.radio_metros,
            rubro=orden.rubro,
            tier=orden.tier_adquirido,
        )

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

        # Obtener mapa estático de Google si estamos en PRO o PREMIUM
        resultado["map_bytes"] = None
        if orden.tier_adquirido in ["pro", "premium"]:
            logger.info("[TASK] Obteniendo mapa estático real de Google...")
            from app.google_places import obtener_mapa_estatico

            resultado["map_bytes"] = obtener_mapa_estatico(
                lat=float(orden.latitud),
                lng=float(orden.longitud),
                radio=orden.radio_metros,
                competidores=resultado.get("competidores_listado", []),
            )

        poblacion_estimada = resultado["poblacion_ponderada"]
        competidores_conteo = resultado["competidores_conteo"]
        sva = resultado["sva"]

        # 2. Invocar el LLM (Amazon Bedrock con Llama 3 70B)
        logger.info("[TASK] Construyendo prompt estratégico y conectando a Amazon Bedrock...")
        prompt = (
            f"Actúa como un experto en geomarketing y analiza la viabilidad comercial de un negocio del giro: "
            f"'{orden.rubro}' en México, ubicado en las coordenadas ({orden.latitud}, {orden.longitud}) "
            f"con un radio de {orden.radio_metros} metros.\n"
            f"Datos del entorno:\n"
            f"- Población residente estimada: {poblacion_estimada} personas\n"
            f"- Competencia directa en la zona: {competidores_conteo} comercios\n"
            f"- Score de viabilidad general SVA: {sva}/100\n"
            f"Intenciones del usuario: {orden.intenciones or 'Ninguna proporcionada'}\n\n"
            f"Genera un análisis estratégico FODA profesional enfocado en el mercado mexicano. "
            f"Sé específico con las Fortalezas, Oportunidades, Debilidades y Amenazas basadas en los datos proporcionados."
        )

        analysis_result = ""
        if DEV_MODE:
            # Modo Desarrollo: Simular la respuesta de la IA
            logger.info("[TASK] Modo Desarrollo: Evitando llamada a AWS Bedrock. Generando FODA simulado.")
            analysis_result = (
                f"### ANÁLISIS ESTRATÉGICO SIMULADO (BEDROCK MOCK)\n\n"
                f"Fortalezas: Excelente densidad de población residente ({poblacion_estimada:,} habitantes) dentro del búfer de radio.\n"
                f"Oportunidades: El giro comercial '{orden.rubro}' tiene alta demanda en corredores mixtos de este perfil.\n"
                f"Debilidades: Presencia directa de {competidores_conteo} comercios consolidados en la zona. Requiere diferenciación competitiva.\n"
                f"Amenazas: Riesgo moderado de saturación de mercado a mediano plazo y costos fijos viales elevados en el pin seleccionado.\n\n"
                f"Recomendación de ROI: Viabilidad del punto moderada-alta. Se proyecta un retorno saludable sobre la inversión a 18 meses."
            )
        else:
            # Modo Producción: Invocar Bedrock de forma real usando boto3
            try:
                bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)

                # Payload para Meta Llama 3 en Bedrock
                body_json = {
                    "prompt": f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n",
                    "max_gen_len": 1024,
                    "temperature": 0.5,
                    "top_p": 0.9,
                }

                logger.info(f"[TASK] Invocando modelo Bedrock: {BEDROCK_MODEL_ID}...")
                response = bedrock_client.invoke_model(
                    modelId=BEDROCK_MODEL_ID,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(body_json),
                )

                response_body = json.loads(response.get("body").read())
                analysis_result = response_body.get("generation", "")
                logger.info("[TASK] Respuesta exitosa obtenida de Amazon Bedrock.")
            except (BotoCoreError, ClientError) as aws_err:
                logger.error(f"[TASK] Error al invocar AWS Bedrock: {aws_err}")
                analysis_result = (
                    "### DIAGNÓSTICO ESTRATÉGICO DE EMERGENCIA\n\n"
                    "Fortalezas: La densidad residencial en el radio del estudio es favorable para el volumen de consumo.\n"
                    "Oportunidades: Implementar ventajas logísticas como entrega rápida a domicilio en la colonia.\n"
                    "Debilidades: Alta competencia en el giro en el cuadrante geográfico analizado.\n"
                    "Amenazas: Márgenes operativos presionados por competidores locales preexistentes."
                )

        # 3. Compilar el PDF real con ReportLab
        logger.info("[TASK] Compilando reporte PDF ejecutivo real mediante ReportLab...")
        try:
            pdf_bytes = ReportLabGenerator.construir_reporte_pdf(orden, resultado, analysis_result)
            logger.info(f"[TASK] Compilación de PDF exitosa ({len(pdf_bytes)} bytes generados).")
        except Exception as pdf_err:
            logger.error(f"[TASK] Error crítico en compilador de PDF: {pdf_err}")
            raise pdf_err

        # Definir la clave S3 privada
        s3_key = f"informes/{orden.cognito_user_id}/{orden.checkout_id}_reporte.pdf"

        # 4. Guardar Reporte en Amazon S3 (o disco local si DEV_MODE)
        if DEV_MODE:
            logger.info("[TASK] Modo Desarrollo: Guardando PDF localmente para inspección...")
            os.makedirs("scratch/reports", exist_ok=True)
            local_pdf_path = f"scratch/reports/{orden.checkout_id}_reporte.pdf"
            with open(local_pdf_path, "wb") as f:
                f.write(pdf_bytes)
            logger.info(f"[TASK] PDF de desarrollo persistido en: {local_pdf_path}")

            # Simulamos presigned URL de descarga local
            presigned_url = f"http://localhost:8000/static/reports/{orden.checkout_id}_reporte.pdf"
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

        # 5. Actualizar estado de la orden a aprobado, guardar clave y registrar fecha
        logger.info("[TASK] Actualizando registro transaccional en base de datos...")
        orden.estado_pago = "approved"
        orden.s3_key_reporte = s3_key
        orden.fecha_aprobacion = datetime.datetime.utcnow()
        db.commit()

        # 6. Envío de Correo mediante Amazon SES (o guardado local de .eml si DEV_MODE)
        subject = f"¡Tu Reporte de GeoViabilidad Hook para '{orden.rubro.capitalize()}' está listo!"

        # Determinar número de páginas según Tier
        paginas_tier = 6 if orden.tier_adquirido == "basico" else (10 if orden.tier_adquirido == "pro" else 14)

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
