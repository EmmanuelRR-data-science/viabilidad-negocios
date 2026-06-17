import logging

import requests

from app.config import BESTTIME_API_KEY, DEV_MODE

logger = logging.getLogger("besttime")

DIAS_SEMANA_ESP = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# BestTime entrega 'day_raw' con 24 valores horarios que inician a las 6:00 AM
# (no a medianoche), por lo que se requiere desplazar los índices al normalizar.
_BESTTIME_HORA_INICIO_DIA = 6


def _normalizar_curva_a_medianoche(day_raw: list) -> list:
    """
    Convierte la curva 'day_raw' de BestTime (24 valores iniciando a las 6:00 AM)
    a una curva indexada por hora real del día (índice 0 = 00:00, ..., 23 = 23:00).
    """
    curva = [0] * 24
    for i, val in enumerate(day_raw[:24]):
        hora_real = (_BESTTIME_HORA_INICIO_DIA + i) % 24
        curva[hora_real] = int(val) if isinstance(val, (int, float)) else 0
    return curva


def _parsear_analysis_besttime(analysis: list) -> dict | None:
    """
    Parsea la lista 'analysis' del forecast de BestTime: un objeto por día de la semana,
    cada uno con 'day_info' (day_int 0=Lunes..6=Domingo, day_mean) y 'day_raw'.
    Retorna la estructura interna midnight-based, o None si no hay curvas utilizables.
    """
    afluencia_semanal: dict[str, list] = {}
    medias_por_dia: dict[str, float] = {}
    hora_pico_por_dia: dict[str, int | None] = {}

    for day_data in analysis:
        if not isinstance(day_data, dict):
            continue
        day_info = day_data.get("day_info") or {}
        day_int = day_info.get("day_int")
        day_raw = day_data.get("day_raw")
        if not isinstance(day_int, int) or not (0 <= day_int <= 6):
            continue
        if not isinstance(day_raw, list) or len(day_raw) < 24:
            continue

        dia_esp = DIAS_SEMANA_ESP[day_int]
        curva = _normalizar_curva_a_medianoche(day_raw)
        afluencia_semanal[dia_esp] = curva

        media = day_info.get("day_mean")
        medias_por_dia[dia_esp] = float(media) if isinstance(media, (int, float)) else sum(curva) / 24.0

        # 'peak_hours' trae horas en reloj de 24h (ej. peak_max = 13 → 13:00)
        peak_hours = day_data.get("peak_hours") or []
        peak_max = peak_hours[0].get("peak_max") if peak_hours and isinstance(peak_hours[0], dict) else None
        hora_pico_por_dia[dia_esp] = peak_max if isinstance(peak_max, int) and 0 <= peak_max <= 23 else None

    if not afluencia_semanal:
        return None

    dia_pico = max(medias_por_dia, key=lambda d: medias_por_dia[d])
    curva_dia_pico = afluencia_semanal[dia_pico]

    hora_pico = hora_pico_por_dia.get(dia_pico)
    if hora_pico is None:
        hora_pico = curva_dia_pico.index(max(curva_dia_pico))

    saturacion_promedio = round(sum(medias_por_dia.values()) / len(medias_por_dia), 1)

    return {
        "afluencia_horaria": curva_dia_pico,
        "afluencia_semanal": afluencia_semanal,
        "dia_pico": dia_pico,
        "hora_pico": f"{hora_pico:02d}:00",
        "saturación_promedio": saturacion_promedio,
    }


def construir_filas_horas_pico(afl_data: dict) -> list[tuple[str, str, str, str]]:
    """
    Construye filas [día, horas pico, horas tranquilas, interpretación]
    a partir de afluencia_semanal real de BestTime (índice 0 = 00:00).
    """
    semanal = afl_data.get("afluencia_semanal") or {}
    filas: list[tuple[str, str, str, str]] = []

    for dia in DIAS_SEMANA_ESP:
        curva = semanal.get(dia)
        if not isinstance(curva, list) or len(curva) < 24:
            continue

        por_hora = [(h, float(curva[h])) for h in range(24)]
        activas = [p for p in por_hora if p[1] > 0]
        if not activas:
            continue

        activas.sort(key=lambda x: x[1], reverse=True)
        picos = [f"{h:02d}:00" for h, _ in activas[:3]]

        tranquilas = sorted(por_hora, key=lambda x: (x[1], x[0]))[:2]
        horas_tranquilas = [f"{h:02d}:00" for h, _ in tranquilas]

        media = sum(v for _, v in por_hora) / 24.0
        maximo = max(v for _, v in por_hora)
        if maximo <= 0:
            interpretacion = "Sin datos"
        elif media >= maximo * 0.55:
            interpretacion = "Afluencia alta"
        elif media >= maximo * 0.25:
            interpretacion = "Afluencia moderada"
        else:
            interpretacion = "Baja afluencia"

        filas.append((dia, ", ".join(picos), ", ".join(horas_tranquilas), interpretacion))

    return filas


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

    # Generar afluencia semanal
    dias_esp = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    afluencia_semanal = {}
    for idx, esp in enumerate(dias_esp):
        shift = idx % 3
        factor = 1.15 if esp in ["Viernes", "Sábado"] else (0.75 if esp == "Domingo" else 1.0)
        daily_curve = []
        for val in curva_afluencia:
            new_val = min(100, int(val * factor))
            daily_curve.append(new_val)
        if shift > 0:
            daily_curve = daily_curve[shift:] + daily_curve[:shift]
        afluencia_semanal[esp] = daily_curve

    return {
        "status": "success",
        "venue_name": f"Zona Comercial - {rubro.capitalize()}",
        "afluencia_horaria": curva_afluencia,
        "afluencia_semanal": afluencia_semanal,
        "dia_pico": "Viernes",
        "hora_pico": "18:00",
        "saturación_promedio": 68.5,
    }


# Máximo de venues a intentar por consulta para controlar el consumo de créditos
_BESTTIME_MAX_INTENTOS = 3


def _solicitar_forecast_besttime(venue_name: str, venue_address: str) -> dict | None:
    """
    Solicita un forecast a BestTime para un venue específico y lo parsea.
    Retorna el dict interno de afluencia, o None si el venue no tiene telemetría
    (404 venue not found, curvas vacías, errores de red, etc.).
    """
    url = "https://besttime.app/api/v1/forecasts"
    query_params = {"api_key_private": BESTTIME_API_KEY, "venue_name": venue_name, "venue_address": venue_address}

    try:
        logger.info(f"Solicitando forecast BestTime para venue '{venue_name}' en '{venue_address}'...")
        response = requests.post(url, params=query_params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # BestTime entrega 'analysis' como lista de 7 objetos (uno por día de la semana)
        if data.get("status") == "OK" and isinstance(data.get("analysis"), list):
            parsed = _parsear_analysis_besttime(data["analysis"])
            if parsed:
                return {
                    "status": "success",
                    "venue_name": data.get("venue_info", {}).get("venue_name", venue_name),
                    **parsed,
                }
        logger.warning(f"BestTime sin curvas utilizables para venue '{venue_name}'. Probando siguiente candidato.")
        return None

    except Exception as e:
        logger.warning(f"BestTime falló para venue '{venue_name}': {e}. Probando siguiente candidato.")
        return None


def obtener_afluencia(lat: float, lng: float, rubro: str, competidores: list | None = None) -> dict:
    """
    Consume la API de BestTime (Foot Traffic Analysis) para recuperar la saturación de
    personas y afluencia por hora para el nicho correspondiente en la coordenada seleccionada.

    BestTime solo tiene telemetría para venues con suficiente popularidad, por lo que se
    intenta con varios competidores de la zona (los más reseñados primero) hasta obtener datos.
    """
    if not BESTTIME_API_KEY or BESTTIME_API_KEY.startswith("pega_tu") or "tu_token" in BESTTIME_API_KEY:
        if DEV_MODE:
            logger.info(f"[DEV_MODE] BestTime key no configurada. Retornando curvas simuladas para el rubro: {rubro}.")
            return obtener_afluencia_simulada(rubro)
        else:
            logger.warning("BestTime API key no configurada en producción. Sección de Afluencia se omitirá.")
            return _sin_cobertura_besttime()

    # Construir candidatos: competidores con nombre y dirección utilizables, ordenados por
    # popularidad (user_ratings_total) — los venues populares son los que BestTime conoce.
    candidatos: list[tuple[str, str]] = []
    if competidores:
        utilizables = [
            c
            for c in competidores
            if c.get("nombre") and c.get("direccion") and c.get("direccion") != "Dirección no disponible"
        ]
        utilizables.sort(key=lambda c: c.get("user_ratings_total", 0), reverse=True)
        candidatos = [(c["nombre"], c["direccion"]) for c in utilizables[:_BESTTIME_MAX_INTENTOS]]

    if not candidatos:
        candidatos = [(f"Zona {rubro}", f"{lat},{lng}")]

    logger.info(
        f"Consultando BestTime API para coordenadas ({lat}, {lng}) y rubro '{rubro}' "
        f"con {len(candidatos)} venue(s) candidato(s)..."
    )
    for venue_name, venue_address in candidatos:
        resultado = _solicitar_forecast_besttime(venue_name, venue_address)
        if resultado:
            return resultado

    logger.error(
        f"Ningún venue candidato de BestTime tiene telemetría en la zona ({lat}, {lng}). "
        "La sección de Afluencia Peatonal será omitida."
    )
    return _sin_cobertura_besttime()
