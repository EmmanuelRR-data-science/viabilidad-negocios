import datetime
import logging
import os

from sqlalchemy.orm import Session

from app.clients.v0.database import OrdenPago, SessionLocal
from app.clients.v0.s3.s3_client_raw import generar_presigned_url_simple, subir_objeto_s3
from app.clients.v0.ses import enviar_email_html
from app.core.config import (
    LOCAL_REPORTS_DIR,
    PUBLIC_APP_URL,
    REPORTS_LOCAL_STORAGE,
    S3_REPORTS_BUCKET,
)
from app.services.tiers import get_tier_strategy
from app.services.v0.analytics.analytics_service import procesar_calculo_analitico
from app.services.v0.reports.report_pdf_service import ReportLabGenerator

logger = logging.getLogger("report_job")


def generar_informe_task(orden_id: int):
    """
    Tarea en segundo plano de FastAPI que ejecuta la recopilación demográfica de PostGIS,
    invoca a Amazon Bedrock para generar el análisis FODA interactivo en base a las intenciones del usuario,
    compila el reporte PDF real con ReportLab y lo guarda de forma segura en Amazon S3.
    Finalmente, envía una confirmación con un enlace de descarga seguro al cliente vía Amazon SES.
    """
    logger.info(f"--- [TASK] Iniciando procesamiento asíncrono para Orden ID: {orden_id} ---")

    db: Session = SessionLocal()
    try:
        orden = db.query(OrdenPago).filter(OrdenPago.id == orden_id).first()
        if not orden:
            logger.error(f"[TASK] Orden con ID {orden_id} no encontrada en la base de datos.")
            return

        strategy = get_tier_strategy(orden.tier_adquirido)
        if orden.tier_adquirido != strategy.tier_id:
            logger.warning(
                "[TASK] Tier normalizado para orden %s: %r -> %s",
                orden.id,
                orden.tier_adquirido,
                strategy.tier_id,
            )
            orden.tier_adquirido = strategy.tier_id

        import json

        competidores_sel = json.loads(orden.competidores_seleccionados) if orden.competidores_seleccionados else None
        aliados_sel = json.loads(orden.aliados_seleccionados) if orden.aliados_seleccionados else None
        config_guiada = json.loads(orden.config_aliados_guiados) if orden.config_aliados_guiados else None
        modo_aliados = getattr(orden, "modo_analisis_aliados", None) or "automatico"
        if strategy.uses_aliados_guiados() and modo_aliados == "guiado" and config_guiada:
            aliados_sel = config_guiada.get("atractores_confirmados")
        elif not strategy.uses_aliados_guiados():
            modo_aliados = "automatico"
            config_guiada = None
            aliados_sel = None

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
        resultado["radio_metros"] = orden.radio_metros
        resultado["tier_adquirido"] = orden.tier_adquirido

        import math

        from app.clients.v0.database import obtener_demografia_ponderada

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

        from app.clients.v0.google import obtener_direccion

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

        resultado["map_bytes"] = None
        if strategy.includes_static_map():
            logger.info("[TASK] Generando mapa de alta resolución para el PDF...")
            from app.clients.v0.google import obtener_mapa_estatico
            from app.services.presentation.maps import generar_mapa_reporte

            incluir_aliados = strategy.includes_aliados_on_map()
            map_bytes = generar_mapa_reporte(
                lat=float(orden.latitud),
                lng=float(orden.longitud),
                radio=orden.radio_metros,
                competidores=resultado.get("competidores_listado", []),
                aliados=resultado.get("aliados_destacados") or resultado.get("aliados_listado", []),
                incluir_aliados=incluir_aliados,
            )
            if not map_bytes:
                map_bytes = obtener_mapa_estatico(
                    lat=float(orden.latitud),
                    lng=float(orden.longitud),
                    radio=orden.radio_metros,
                    competidores=resultado.get("competidores_listado", []),
                    aliados=resultado.get("aliados_destacados") or resultado.get("aliados_listado", []),
                    incluir_aliados=incluir_aliados,
                )
            resultado["map_bytes"] = map_bytes

        poblacion_estimada = resultado["poblacion_ponderada"]
        competidores_conteo = resultado["competidores_conteo"]
        sva = resultado["sva"]

        logger.info("[TASK] Generando diagnóstico estratégico (Groq o respaldo cuantitativo)...")
        from app.services.foda_service import foda_respaldo_cuantitativo as _foda_respaldo_cuantitativo
        from app.services.foda_service import generar_analisis_foda

        if strategy.uses_bedrock():
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
        else:
            logger.info("[TASK] Tier %s sin Bedrock: usando respaldo cuantitativo.", strategy.tier_id)
            analysis_result = _foda_respaldo_cuantitativo(
                resultado,
                orden.rubro,
                comp_adicionales=orden.competidores_adicionales,
                aliados_adicionales=orden.aliados_adicionales,
            )

        logger.info("[TASK] Compilando reporte PDF ejecutivo real mediante ReportLab...")
        try:
            pdf_bytes = ReportLabGenerator.construir_reporte_pdf(orden, resultado, analysis_result)
            logger.info(f"[TASK] Compilación de PDF exitosa ({len(pdf_bytes)} bytes generados).")
        except Exception as pdf_err:
            logger.error(f"[TASK] Error crítico en compilador de PDF: {pdf_err}")
            raise pdf_err

        import re

        rubro_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", orden.rubro.lower()).strip("_")
        s3_key = f"informes/{orden.cognito_user_id}/{orden.checkout_id}_reporte_{rubro_slug}.pdf"

        if REPORTS_LOCAL_STORAGE:
            logger.info("[TASK] Guardando PDF en almacenamiento local...")
            os.makedirs(LOCAL_REPORTS_DIR, exist_ok=True)
            local_pdf_path = f"{LOCAL_REPORTS_DIR}/{orden.checkout_id}_reporte_{rubro_slug}.pdf"
            with open(local_pdf_path, "wb") as f:
                f.write(pdf_bytes)
            logger.info("[TASK] PDF persistido en: %s", local_pdf_path)

            app_base = (PUBLIC_APP_URL or "http://localhost:8000").rstrip("/")
            # Sin URL pública directa al PDF: el usuario descarga autenticado en la app.
            presigned_url = f"{app_base}/?orden_id={orden.id}"
        else:
            logger.info(f"[TASK] Guardando reporte PDF en S3: s3://{S3_REPORTS_BUCKET}/{s3_key}")
            if subir_objeto_s3(S3_REPORTS_BUCKET, s3_key, pdf_bytes):
                presigned_url = (
                    generar_presigned_url_simple(S3_REPORTS_BUCKET, s3_key)
                    or "https://geoviabilidad.com/reportes/descarga-directa"
                )
            else:
                presigned_url = "https://geoviabilidad.com/reportes/descarga-directa"

        logger.info("[TASK] Actualizando registro transaccional en base de datos con caché del reporte...")
        import json

        orden.estado_pago = "approved"
        orden.s3_key_reporte = s3_key
        foda_para_cache = {k: v for k, v in analysis_result.items() if k == "_fuente" or not str(k).startswith("_")}
        orden.resultado_json = json.dumps(resultado, default=str)
        orden.foda_json = json.dumps(foda_para_cache, default=str)
        orden.fecha_aprobacion = datetime.datetime.utcnow()
        db.commit()

        subject = f"¡Tu Reporte de GeoViabilidad Hook para '{orden.rubro.capitalize()}' está listo!"
        paginas_tier = strategy.pdf_pages()

        html_body = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    color: #334155; line-height: 1.6; margin: 0; padding: 0;
                    background-color: #f8fafc;
                }}
                .container {{
                    max-width: 600px; margin: 30px auto; background: #ffffff;
                    border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;
                    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
                }}
                .header {{ background-color: #0f172a; padding: 40px 30px; text-align: center; color: #ffffff; }}
                .header h1 {{ margin: 0; font-size: 24px; font-weight: bold; letter-spacing: 0.5px; }}
                .content {{ padding: 30px; }}
                .kpi-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                .kpi-table td {{
                    border: 1px solid #e2e8f0; padding: 12px; text-align: center;
                    background-color: #f1f5f9;
                }}
                .kpi-val {{ font-size: 20px; font-weight: bold; color: #2563eb; }}
                .kpi-lbl {{ font-size: 10px; font-weight: bold; color: #64748b; text-transform: uppercase; }}
                .btn {{
                    display: inline-block; padding: 14px 28px; background-color: #2563eb;
                    color: #ffffff !important; text-decoration: none; border-radius: 6px;
                    font-weight: bold; text-align: center; margin: 25px 0;
                }}
                .footer {{
                    background-color: #f1f5f9; padding: 20px; text-align: center;
                    font-size: 11px; color: #64748b; border-top: 1px solid #e2e8f0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>GEOVIABILIDAD HOOK</h1>
                </div>
                <div class="content">
                    <p>Estimado/a cliente,</p>
                    <p>Nos complace notificarte que tu estudio de
                    <b>Localización Inteligente y Geomarketing</b> ha sido procesado de forma exitosa.</p>
                    <p>Tu reporte ejecutivo en formato PDF de <b>{paginas_tier} páginas</b> ha sido compilado
                    para el giro comercial <b>'{orden.rubro}'</b> en base a los datos demográficos espaciales
                    de INEGI.</p>
                    
                    <table class="kpi-table">
                        <tr>
                            <td><span class="kpi-lbl">Score SVA</span><br/>
                                <span class="kpi-val">{sva}/100</span></td>
                            <td><span class="kpi-lbl">Población Residente</span><br/>
                                <span class="kpi-val">{poblacion_estimada:,} hab.</span></td>
                            <td><span class="kpi-lbl">Competidores</span><br/>
                                <span class="kpi-val">{competidores_conteo}</span></td>
                        </tr>
                    </table>

                    <p>Puedes descargar tu informe PDF encriptado de forma segura y directa haciendo clic
                    en el siguiente botón. Este enlace tiene una <b>vigencia de 24 horas</b> por motivos
                    de seguridad corporativa:</p>
                    
                    <div style="text-align: center;">
                        <a href="{presigned_url}" class="btn" target="_blank">DESCARGAR REPORTE PDF</a>
                    </div>
                    
                    <p>Si el enlace expira, siempre podrás ingresar al dashboard interactivo de la plataforma
                    utilizando tu cuenta y generar un nuevo acceso.</p>
                    <p>Atentamente,<br/><b>El equipo de Data Science de GeoViabilidad Hook</b></p>
                </div>
                <div class="footer">
                    Este es un correo automático confidencial. Si recibiste este mensaje por error,
                    por favor notifícanos de inmediato.
                </div>
            </div>
        </body>
        </html>
        """

        enviar_email_html(orden.email, subject, html_body, orden_id=orden.id)

        logger.info(f"[TASK] --- ¡INFORME COMPLETADO CON ÉXITO PARA LA ORDEN {orden.id}! ---")

    except Exception as e:
        logger.exception(f"[TASK] Error catastrófico en la tarea en segundo plano: {e}")
        db.rollback()
    finally:
        db.close()
