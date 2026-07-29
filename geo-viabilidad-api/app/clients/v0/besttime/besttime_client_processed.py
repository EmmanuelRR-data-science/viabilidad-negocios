from __future__ import annotations

import logging

from app.clients.v0.besttime.besttime_client_raw import (
    api_key_besttime_valida,
    solicitar_forecast_besttime_raw,
)
from app.core.config import DEV_MODE
from app.schemas.v0.besttime.besttime_domain_schemas import (
    AfluenciaDiaDomain,
    AfluenciaDomain,
)

logger = logging.getLogger("besttime_client_processed")

DIAS_SEMANA_ESP = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
_BESTTIME_HORA_INICIO_DIA = 6
_BESTTIME_MAX_INTENTOS = 2


def _normalizar_curva_a_medianoche(day_raw: list) -> list[int]:
    curva = [0] * 24
    for i, val in enumerate(day_raw[:24]):
        hora_real = (_BESTTIME_HORA_INICIO_DIA + i) % 24
        curva[hora_real] = int(val) if isinstance(val, (int, float)) else 0
    return curva


def _parsear_analysis_besttime(analysis: list) -> dict | None:
    afluencia_semanal = {}
    medias_por_dia = {}
    hora_pico_por_dia = {}

    for day_data in analysis:
        day_info = day_data.day_info
        day_int = day_info.day_int
        day_raw = day_data.day_raw
        if day_int is None or not (0 <= day_int <= 6):
            continue
        if not day_raw or len(day_raw) < 24:
            continue

        dia_esp = DIAS_SEMANA_ESP[day_int]
        curva = _normalizar_curva_a_medianoche(day_raw)
        afluencia_semanal[dia_esp] = curva

        media = day_info.day_mean
        medias_por_dia[dia_esp] = float(media) if media is not None else sum(curva) / 24.0

        # En el DTO, peak_hours no se mapeó de forma estricta, lo extraemos si existe en el modelo base o calculamos
        hora_pico_por_dia[dia_esp] = None

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
    semanal = afl_data.get("afluencia_semanal") or {}
    filas = []

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


def _sin_cobertura_besttime() -> AfluenciaDomain:
    return AfluenciaDomain(status="no_data")


def obtener_afluencia_simulada(rubro: str) -> AfluenciaDomain:
    curva_afluencia = [
        0,
        0,
        0,
        0,
        0,
        2,
        10,
        25,
        45,
        55,
        60,
        70,
        85,
        90,
        80,
        65,
        75,
        88,
        95,
        80,
        50,
        25,
        10,
        2,
    ]
    if "gym" in rubro.lower() or "gimnasio" in rubro.lower():
        curva_afluencia = [0, 0, 0, 0, 0, 15, 75, 90, 65, 30, 25, 20, 20, 25, 35, 45, 60, 85, 95, 70, 40, 20, 10, 0]

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

    semanal_domain = [
        AfluenciaDiaDomain(
            dia=d, dia_int=dias_esp.index(d), media=sum(afluencia_semanal[d]) / 24.0, maximo=max(afluencia_semanal[d])
        )
        for d in dias_esp
    ]

    return AfluenciaDomain(
        status="success",
        venue_name=f"Zona Comercial - {rubro.capitalize()}",
        afluencia_semanal=semanal_domain,
        afluencia_horaria=curva_afluencia,
        dia_pico="Viernes",
        hora_pico="18:00",
        saturación_promedio=68.5,
    )


def obtener_afluencia(lat: float, lng: float, rubro: str, competidores: list | None = None) -> dict:
    """Invoca la API de BestTime y procesa a la estructura del dominio."""
    if not api_key_besttime_valida():
        if DEV_MODE:
            logger.info("[DEV_MODE] BestTime key no configurada. Retornando curvas simuladas.")
            sim = obtener_afluencia_simulada(rubro)
            curva = [int(v) for v in sim.afluencia_horaria]
            return {
                "status": sim.status,
                "venue_name": sim.venue_name,
                "afluencia_horaria": curva,
                "afluencia_semanal": dict.fromkeys(DIAS_SEMANA_ESP, curva),
                "dia_pico": sim.dia_pico,
                "hora_pico": sim.hora_pico,
                "saturación_promedio": sim.saturación_promedio,
            }
        return _sin_cobertura_besttime().model_dump()

    candidatos = []
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

    for venue_name, venue_address in candidatos:
        dto = solicitar_forecast_besttime_raw(venue_name, venue_address)
        if dto and dto.status == "OK" and dto.analysis:
            parsed = _parsear_analysis_besttime(dto.analysis)
            if parsed:
                return {
                    "status": "success",
                    "venue_name": dto.venue_info.get("venue_name", venue_name) if dto.venue_info else venue_name,
                    **parsed,
                }

    return _sin_cobertura_besttime().model_dump()
