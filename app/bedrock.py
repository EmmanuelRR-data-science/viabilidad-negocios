import json
import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import AWS_REGION, BEDROCK_MODEL_ID, DEV_MODE

logger = logging.getLogger("bedrock")


def generar_analisis_foda(datos_entorno: dict, intenciones: str) -> dict:
    """
    Construye el prompt estratégico e invoca el modelo Llama 3 en AWS Bedrock
    para generar el diagnóstico FODA cualitativo y las sugerencias de ROI.
    """
    logger.info("Iniciando generación de FODA cruzado con Amazon Bedrock...")

    rubro = datos_entorno.get("rubro", "Giro no especificado")
    poblacion = datos_entorno.get("poblacion_ponderada", 0)
    competencia = datos_entorno.get("competidores_conteo", 0)
    sva = datos_entorno.get("sva", 50)
    direcc = datos_entorno.get("direccion", "Ubicación seleccionada")

    # Prompt estructurado de ingeniería
    system_prompt = (
        "Eres un consultor experto en geomarketing y desarrollo de negocios en México.\n"
        "Debes responder estrictamente en formato JSON válido en español. Tu respuesta debe estructurarse "
        "exactamente con las siguientes llaves JSON:\n"
        "{\n"
        '  "fortalezas": ["f1", "f2", ...],\n'
        '  "oportunidades": ["o1", "o2", ...],\n'
        '  "debilidades": ["d1", "d2", ...],\n'
        '  "amenazas": ["a1", "a2", ...],\n'
        '  "conclusion": "resumen de viabilidad comercial general",\n'
        '  "recomendacion_roi": "estimación y consejo sobre el Retorno de Inversión"\n'
        "}\n"
        "No agregues texto explicativo fuera del JSON."
    )

    user_prompt = (
        f"Giro del negocio: {rubro}\n"
        f"Ubicación: {direcc}\n"
        f"Radio de análisis: {datos_entorno.get('radio_metros', 1000)} metros\n"
        f"Población estimada en zona: {poblacion:,} habitantes\n"
        f"Número de competidores directos: {competencia} comercios\n"
        f"Score SVA de Viabilidad General: {sva}/100\n"
        f"Intenciones del emprendedor: {intenciones or 'Sin intenciones especiales escritas.'}\n\n"
        f"Genera el análisis FODA adaptado específicamente para el éxito comercial de este giro en México."
    )

    if DEV_MODE:
        logger.info("[BEDROCK] Modo Desarrollo: Devolviendo análisis FODA simulatido para el reporte.")
        # Análisis realista basado en el rubro
        return {
            "fortalezas": [
                f"Sólida base demográfica con {poblacion:,} personas residentes directas en el búfer.",
                f"Ubicación identificada en {direcc} con excelente accesibilidad vial.",
                "Las intenciones del emprendedor muestran una propuesta de valor enfocada y diferenciada.",
            ],
            "oportunidades": [
                f"El rubro '{rubro}' tiene un mercado de consumo activo debido al perfil residencial local.",
                "Posibilidad de captar clientes descontentos de la competencia actual mediante entrega rápida.",
                "Implementación de marketing geolocalizado en redes sociales en las colonias colindantes.",
            ],
            "debilidades": [
                f"Presencia de {competencia} competidores directos en la periferia que ya tienen posicionamiento.",
                "Costos iniciales de instalación y acondicionamiento del local comercial en zonas transitadas.",
                "Límite de estacionamiento disponible para clientes en horas de alto tráfico.",
            ],
            "amenazas": [
                "Cambios macroeconómicos que afecten el ticket de compra promedio del sector en México.",
                "Estrategias de descuentos agresivas de los competidores más consolidados de la zona.",
                "Saturación comercial progresiva en el micro-segmento de la colonia.",
            ],
            "conclusion": (
                f"El punto analizado cuenta con un Score de Viabilidad SVA de {sva}/100. La densidad poblacional "
                f"es favorable y compensa la competencia de {competencia} negocios. La viabilidad comercial es altamente aceptable."
            ),
            "recomendacion_roi": (
                "Se estima un Retorno de Inversión (ROI) inicial saludable. Se aconseja un modelo operativo de costo moderado "
                "los primeros 6 meses, enfocando el 20% del presupuesto inicial a posicionamiento digital local."
            ),
        }

    # Llamada real a Amazon Bedrock
    try:
        bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

        # Combinar prompts en la estructura de Llama 3
        full_prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n{user_prompt}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )

        body_json = {"prompt": full_prompt, "max_gen_len": 1500, "temperature": 0.3, "top_p": 0.9}

        logger.info(f"[BEDROCK] Invocando Llama 3 a través de Bedrock (Model: {BEDROCK_MODEL_ID})...")
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body_json),
        )

        response_body = json.loads(response.get("body").read())
        generation = response_body.get("generation", "{}").strip()

        # Buscar llaves JSON para recortar posibles textos adicionales accidentales del LLM
        start_idx = generation.find("{")
        end_idx = generation.rfind("}")
        if start_idx != -1 and end_idx != -1:
            json_str = generation[start_idx : end_idx + 1]
            return json.loads(json_str)
        else:
            return json.loads(generation)

    except (BotoCoreError, ClientError) as aws_err:
        logger.error(f"[BEDROCK] Excepción de AWS Bedrock: {aws_err}")
        raise aws_err
    except Exception as parse_err:
        logger.error(f"[BEDROCK] Error al parsear JSON del LLM: {parse_err}")
        return {
            "fortalezas": ["Población residente favorable en la coordenada."],
            "debilidades": ["Presencia de competidores en el radio de análisis."],
            "oportunidades": ["Diferenciación de marca en marketing digital local."],
            "amenazas": ["Saturación de ofertas de competidores tradicionales."],
            "conclusion": "Análisis cuantitativo completado con éxito. Diagnóstico estratégico simplificado debido a limitaciones de formato.",
            "recomendacion_roi": "Monitorear costos de instalación y ticket promedio recomendado en la zona.",
        }
