"""Textos y cálculos compartidos para presentar afluencia peatonal (web + PDF)."""

from __future__ import annotations

HORAS_NOCHE = (20, 21, 22, 23)

NOTA_ESTABLECIMIENTO_REFERENCIA = (
    "La afluencia refleja el paso de personas en el establecimiento comercial de referencia "
    "utilizado para la medición (BestTime), no necesariamente el tránsito peatonal general de la calle. "
    "Las horas sin dato reportado (0 %) no se incluyen en el promedio nocturno."
)

ACLARACION_HEATMAP_COMPETIDORES = (
    "<b>Importante:</b> A diferencia de la gráfica de atractores comerciales (aliados) "
    "presentada antes en este reporte, este mapa de calor proviene de la telemetría BestTime "
    "de un <b>competidor</b> identificado en la zona (priorizando el de más reseñas con dato "
    "disponible). No representa el tráfico de bancos, escuelas, transporte u otros aliados."
)

LABEL_NOCHE_PROMEDIO = "Noche — promedio de horas con dato (20:00–23:00)"


def _promedio_rango(curva: list, inicio: int, fin: int) -> int:
    segmento = curva[inicio:fin]
    if not segmento:
        return 0
    return int(round(sum(segmento) / len(segmento)))


def _valor_hora(curva: list, hora: int) -> int:
    if hora < 0 or hora >= len(curva):
        return 0
    return int(curva[hora])


def _formato_intensidad(valor: int) -> str:
    if valor <= 0:
        return "Sin dato"
    return f"{valor}%"


def calcular_desglose_noche(curva: list) -> dict:
    """Desglose 20–23 h y promedio nocturno solo con horas que tienen telemetría (> 0)."""
    por_hora = {hora: _valor_hora(curva, hora) for hora in HORAS_NOCHE}
    con_dato = [v for v in por_hora.values() if v > 0]
    promedio_con_dato = int(round(sum(con_dato) / len(con_dato))) if con_dato else 0
    return {
        "por_hora": por_hora,
        "promedio_con_dato": promedio_con_dato,
        "horas_con_dato": len(con_dato),
    }


def construir_filas_tabla_afluencia(curva: list) -> list[tuple[str, str]]:
    """
    Filas [rango, intensidad] para la tabla resumen.
    Incluye bloques diurnos, desglose hora a hora de la noche y promedio nocturno con dato.
    """
    if len(curva) < 24:
        return []

    filas: list[tuple[str, str]] = [
        ("Mañana (08:00 - 12:00)", f"{_promedio_rango(curva, 8, 12)}%"),
        ("Mediodía (12:00 - 16:00)", f"{_promedio_rango(curva, 12, 16)}%"),
        ("Tarde (16:00 - 20:00)", f"{_promedio_rango(curva, 16, 20)}%"),
    ]

    noche = calcular_desglose_noche(curva)
    filas.append(("Desglose nocturno (competidor de referencia)", ""))
    for hora in HORAS_NOCHE:
        filas.append((f"  {hora:02d}:00", _formato_intensidad(noche["por_hora"][hora])))

    if noche["horas_con_dato"] > 0:
        filas.append((LABEL_NOCHE_PROMEDIO, f"{noche['promedio_con_dato']}%"))
    else:
        filas.append((LABEL_NOCHE_PROMEDIO, "Sin dato"))

    return filas


def texto_establecimiento_referencia(nombre: str | None) -> str:
    if nombre:
        return f"Competidor de referencia para la medición: {nombre}."
    return (
        "Medición basada en el competidor identificado en la zona con telemetría BestTime disponible."
    )
