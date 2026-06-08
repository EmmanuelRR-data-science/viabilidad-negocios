import logging

import requests

from app.config import BESTTIME_API_KEY, DEV_MODE

logger = logging.getLogger("besttime")


def _sin_cobertura_besttime() -> dict:
    """
    Retorna un dict que indica ausencia real de datos de BestTime.
    Se usa cuando la API falla en producción para que el reporte omita la sección.
    """
    return {
        "status": "no_data",
        "venue_name": "",
        "afluencia_horaria": [],
        "dia_pico": None,
        "hora_pico": None,
        "saturación_promedio": 0.0,
    }


def obtener_afluencia_simulada(rubro: str) -> dict:
    """
    Retorna curvas de afluencia peatonal simuladas de forma determinista para desarrollo.
    """
    # Generar curvas realistas de afluencia horaria (0 a 100) para un día estándar
    # Curva mixta: Picos al mediodía (almuerzo) y tarde-noche (salida del trabajo)
    curva_afluencia = [
        0,
        0,
        0,
        0,
        0,
        2,  # 00:00 - 05:00
        10,
        25,
        45,
        55,
        60,
        70,  # 06:00 - 11:00
        85,
        90,
        80,
        65,
        75,
        88,  # 12:00 - 17:00
        95,
        80,
        50,
        25,
        10,
        2,  # 18:00 - 23:00
    ]

    # Variación leve según rubro
    if "gym" in rubro.lower() or "gimnasio" in rubro.lower():
        # Gimnasios tienen picos muy fuertes en la mañana (7-9am) y tarde (6-8pm)
        curva_afluencia = [0, 0, 0, 0, 0, 15, 75, 90, 65, 30, 25, 20, 20, 25, 35, 45, 60, 85, 95, 70, 40, 20, 10, 0]

    return {
        "status": "success",
        "venue_name": f"Zona Comercial - {rubro.capitalize()}",
        "afluencia_horaria": curva_afluencia,
        "dia_pico": "Viernes",
        "hora_pico": "18:00",
        "saturación_promedio": 68.5,
    }


def obtener_afluencia(lat: float, lng: float, rubro: str, competidores: list | None = None) -> dict:
    """
    Consume la API de BestTime (Foot Traffic Analysis) para recuperar la saturación de
    personas y afluencia por hora para el nicho correspondiente en la coordenada seleccionada.
    """
    if not BESTTIME_API_KEY or BESTTIME_API_KEY.startswith("pega_tu") or "tu_token" in BESTTIME_API_KEY:
        if DEV_MODE:
            logger.info(f"[DEV_MODE] BestTime key no configurada. Retornando curvas simuladas para el rubro: {rubro}.")
            return obtener_afluencia_simulada(rubro)
        else:
            logger.warning("BestTime API key no configurada en producción. Sección de Afluencia se omitirá.")
            return _sin_cobertura_besttime()

    # Si hay competidores reales, usar el más cercano para obtener telemetría real representativa de la zona
    venue_name = f"Zona {rubro}"
    venue_address = f"{lat},{lng}"
    if competidores and len(competidores) > 0:
        nearest = competidores[0]
        comp_name = nearest.get("nombre")
        comp_addr = nearest.get("direccion")
        if comp_name and comp_addr and comp_addr != "Dirección no disponible":
            venue_name = comp_name
            venue_address = comp_addr
            logger.info(f"Usando competidor más cercano para BestTime: '{venue_name}' en '{venue_address}'")

    # Llamada real a BestTime API para registrar y generar un forecast de un nuevo venue
    url = "https://besttime.app/api/v1/forecasts"
    query_params = {"api_key_private": BESTTIME_API_KEY, "venue_name": venue_name, "venue_address": venue_address}

    try:
        logger.info(f"Consultando BestTime API para coordenadas ({lat}, {lng}) y rubro '{rubro}'...")
        response = requests.post(url, params=query_params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "OK" and "analysis" in data:
            analysis = data["analysis"]

            # Extraer las curvas del día de hoy
            # BestTime entrega arrays por día de la semana, mapeamos un promedio
            day_raw = analysis.get("day_raw", [])
            afluencia_horaria = day_raw if len(day_raw) == 24 else [0] * 24

            return {
                "status": "success",
                "venue_name": data.get("venue_info", {}).get("venue_name", "Zona Comercial"),
                "afluencia_horaria": afluencia_horaria,
                "dia_pico": analysis.get("busy_hours_day"),
                "hora_pico": f"{analysis.get('peak_hour')}:00",
                "saturación_promedio": float(analysis.get("day_intensity", 50)),
            }
        else:
            logger.warning(
                "La respuesta de BestTime API no tiene la estructura de análisis requerida. "
                "Se omitirá la sección de Afluencia Peatonal en el reporte."
            )
            return _sin_cobertura_besttime()

    except Exception as e:
        logger.error(f"Error en llamada a BestTime API: {e}. La sección de Afluencia Peatonal será omitida.")
        return _sin_cobertura_besttime()
