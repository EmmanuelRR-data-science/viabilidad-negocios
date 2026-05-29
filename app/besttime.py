import logging

import requests

from app.config import BESTTIME_API_KEY, DEV_MODE

logger = logging.getLogger("besttime")


def obtener_afluencia(lat: float, lng: float, rubro: str) -> dict:
    """
    Consume la API de BestTime (Foot Traffic Analysis) para recuperar la saturación de
    personas y afluencia por hora para el nicho correspondiente en la coordenada seleccionada.
    """
    if DEV_MODE or not BESTTIME_API_KEY or BESTTIME_API_KEY.startswith("pega_tu"):
        logger.info(f"Modo Desarrollo: Retornando curvas de afluencia peatonal simuladas para rubro: {rubro}.")

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

    # Llamada real a BestTime API
    # En BestTime, usualmente se busca por coordenadas y se genera una consulta del venue más cercano
    url = "https://besttime.app/api/v1/forecasts/venue"
    params = {"api_key_private": BESTTIME_API_KEY, "venue_name": f"Zona {rubro}", "venue_address": f"{lat},{lng}"}

    try:
        logger.info(f"Consultando BestTime API para coordenadas ({lat}, {lng}) y rubro '{rubro}'...")
        response = requests.post(url, data=params, timeout=10)
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
                "La respuesta de BestTime API no tiene la estructura de análisis requerida. Aplicando fallback de curvas simuladas."
            )
            # Fallback tolerante para no romper la experiencia en producción si expira cuota de BestTime
            return obtener_afluencia(lat, lng, rubro)

    except Exception as e:
        logger.error(f"Error en llamada a BestTime API: {e}. Usando fallback para asegurar usabilidad.")
        return obtener_afluencia(lat, lng, rubro)
