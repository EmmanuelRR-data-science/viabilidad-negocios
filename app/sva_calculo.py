"""
Cálculo transparente del Score de Viabilidad de Apertura (SVA).
Fórmulas compartidas entre analytics y el PDF (sin caja negra).
"""

from __future__ import annotations

import math
from typing import Any

# Referencias de densidad (hab/km²) — calibradas para contexto urbano mexicano.
DENSIDAD_MINIMA_HAB_KM2 = 120.0
DENSIDAD_OPTIMA_HAB_KM2 = 2000.0

PESO_DEMOGRAFICO = 0.4
PESO_COMPETENCIA = 0.3
PESO_TRAFICO = 0.3

ISC_LOG_MIN = -6.0
ISC_LOG_MAX = -2.0
SCORE_TRAFICO_SIN_BESTTIME = 55.0

# Etiqueta unificada del tercer pilar SVA (visible en PDF, dashboard y lecturas).
ETIQUETA_PILAR_TRAFICO = "Tráfico peatonal"

GLOSARIO_SVA_PDF = [
    (
        "ISC (Indice de Saturacion Comercial)",
        "Suma la presion de cada competidor segun su distancia: 1 / distancia^2. "
        "Rivales muy cercanos elevan el ISC mas que muchos rivales lejanos.",
    ),
    (
        "Pesos 40% / 30% / 30%",
        "Demografia aporta hasta 40 puntos, competencia hasta 30 y tráfico peatonal hasta 30. "
        "El SVA es la suma de esos aportes (maximo teorico 100).",
    ),
    (
        "Redondeo del SVA",
        "La suma ponderada puede traer decimales (ej. 78.7); el reporte muestra el entero "
        "mas cercano (ej. 79) para facilitar la lectura.",
    ),
]


def _lectura_llana_demografico(dem: dict[str, Any]) -> str:
    score = float(dem["score"])
    dens = float(dem["densidad_hab_km2"])
    if score >= 80:
        return (
            f"Hay buena concentracion de personas en tu radio ({dens:,.0f} hab/km2); "
            f"el pilar demografico aporta {score:.0f}/100."
        )
    if score >= 50:
        return (
            f"La densidad es aceptable ({dens:,.0f} hab/km2) pero no maxima; "
            f"el pilar demografico queda en {score:.0f}/100."
        )
    return (
        f"Poca poblacion concentrada en el radio ({dens:,.0f} hab/km2); "
        f"el pilar demografico limita el SVA ({score:.0f}/100)."
    )


def _lectura_llana_competencia(comp: dict[str, Any]) -> str:
    n = int(comp["competidores_conteo"])
    score = float(comp["score"])
    if n == 0 or comp["isc"] <= 0:
        return "No hay competidores detectados en el radio; este pilar no resta puntos (100/100)."
    if score >= 80:
        return (
            f"Se detectaron {n} rivales, pero con poca presion muy cercana; "
            f"el pilar de competencia queda alto ({score:.0f}/100)."
        )
    if score >= 50:
        return (
            f"Hay {n} competidores y varios compiten cerca de tu punto; "
            f"por eso el pilar baja a {score:.0f}/100 (no depende solo del numero, sino de la distancia)."
        )
    return (
        f"Alta saturacion: {n} rivales con varios muy proximos; "
        f"el pilar de competencia presiona fuerte el SVA ({score:.0f}/100)."
    )


NOTA_BESTTIME_TRAFICO = (
    "Este dato se extrae de la plataforma BestTime con base en la telemetría del "
    "establecimiento comercial de referencia en la zona, no necesariamente del tránsito peatonal general de la calle."
)


def _lectura_llana_trafico(traf: dict[str, Any], tier: str) -> str:
    score = float(traf["score"])
    if traf.get("medicion_peatonal_real"):
        return (
            f"El tráfico peatonal medido en la zona equivale a {score:.1f}%; "
            f"ese porcentaje es el score del pilar de tráfico peatonal. "
            f"{NOTA_BESTTIME_TRAFICO}"
        )
    return (
        f"No hubo medición de tráfico peatonal en esta coordenada para este reporte; "
        f"se usa un valor base de {score:.0f} en el pilar."
    )


def calcular_isc_desde_competidores(competidores: list[dict]) -> float:
    """ISC = Σ 1 / max(distancia_metros, 10)² — penaliza rivales muy cercanos."""
    isc = 0.0
    for comp in competidores:
        dist = comp.get("distancia_metros")
        if dist is None:
            continue
        dist_cap = max(float(dist), 10.0)
        isc += 1.0 / (dist_cap**2)
    return isc


def calcular_isc_distancias_escaladas(competidores: list[dict], factor: float = 2.0) -> float:
    """ISC si cada rival estuviera a factor x su distancia actual (mismo conteo)."""
    isc = 0.0
    for comp in competidores:
        dist = comp.get("distancia_metros")
        if dist is None:
            continue
        dist_cap = max(float(dist) * factor, 10.0)
        isc += 1.0 / (dist_cap**2)
    return isc


def factor_logaritmico_isc(isc: float) -> float | None:
    if isc <= 0:
        return None
    return math.log10(isc)


def calcular_score_competencia(isc: float) -> float:
    if isc <= 0:
        return 100.0
    factor = math.log10(isc)
    if factor <= ISC_LOG_MIN:
        return 100.0
    if factor >= ISC_LOG_MAX:
        return 10.0
    score = 100.0 - ((factor - ISC_LOG_MIN) / (ISC_LOG_MAX - ISC_LOG_MIN) * 90.0)
    return round(min(100.0, max(0.0, score)), 1)


def calcular_score_demografico(poblacion: int, radio_metros: int) -> tuple[float, float]:
    """
    Pilar demográfico estandarizado por densidad en el radio (hab/km²),
    no por población absoluta.
    """
    radio_km = radio_metros / 1000.0
    area_km2 = math.pi * radio_km * radio_km
    densidad = (poblacion / area_km2) if area_km2 > 0 else 0.0

    if densidad <= DENSIDAD_MINIMA_HAB_KM2:
        score = 15.0
    elif densidad >= DENSIDAD_OPTIMA_HAB_KM2:
        score = 100.0
    else:
        log_d = math.log10(densidad)
        log_min = math.log10(DENSIDAD_MINIMA_HAB_KM2)
        log_opt = math.log10(DENSIDAD_OPTIMA_HAB_KM2)
        score = 15.0 + ((log_d - log_min) / (log_opt - log_min)) * 85.0

    return round(min(100.0, max(0.0, score)), 1), round(densidad, 1)


def componer_sva(score_dem: float, score_comp: float, score_traf: float) -> tuple[float, int]:
    sva = (score_dem * PESO_DEMOGRAFICO) + (score_comp * PESO_COMPETENCIA) + (score_traf * PESO_TRAFICO)
    sva_redondeado = int(round(sva))
    return round(sva, 1), sva_redondeado


def detalle_pilar_demografico(poblacion: int, radio_metros: int) -> dict[str, Any]:
    radio_km = radio_metros / 1000.0
    area_km2 = math.pi * radio_km * radio_km
    densidad = (poblacion / area_km2) if area_km2 > 0 else 0.0
    score, densidad_redondeada = calcular_score_demografico(poblacion, radio_metros)

    if densidad <= DENSIDAD_MINIMA_HAB_KM2:
        regla = f"Densidad <= {DENSIDAD_MINIMA_HAB_KM2:,.0f} hab/km2 -> score fijo 15"
        log_d = log_min = log_opt = None
    elif densidad >= DENSIDAD_OPTIMA_HAB_KM2:
        regla = f"Densidad >= {DENSIDAD_OPTIMA_HAB_KM2:,.0f} hab/km2 -> score fijo 100"
        log_d = log_min = log_opt = None
    else:
        log_d = math.log10(densidad)
        log_min = math.log10(DENSIDAD_MINIMA_HAB_KM2)
        log_opt = math.log10(DENSIDAD_OPTIMA_HAB_KM2)
        regla = (
            f"15 + ((log10(densidad) - log10({DENSIDAD_MINIMA_HAB_KM2:,.0f})) / "
            f"(log10({DENSIDAD_OPTIMA_HAB_KM2:,.0f}) - log10({DENSIDAD_MINIMA_HAB_KM2:,.0f}))) x 85"
        )

    resultado = {
        "poblacion": poblacion,
        "radio_metros": radio_metros,
        "area_km2": round(area_km2, 3),
        "densidad_hab_km2": densidad_redondeada,
        "log_densidad": round(log_d, 4) if log_d is not None else None,
        "regla": regla,
        "score": score,
        "aporte_ponderado": round(score * PESO_DEMOGRAFICO, 1),
    }
    resultado["lectura_llana"] = _lectura_llana_demografico(resultado)
    return resultado


def detalle_pilar_competencia(isc: float, competidores_conteo: int) -> dict[str, Any]:
    factor = factor_logaritmico_isc(isc)
    score = calcular_score_competencia(isc)

    if isc <= 0:
        regla = "Sin competidores -> score fijo 100"
    elif factor is not None and factor <= ISC_LOG_MIN:
        regla = f"log10(ISC) <= {ISC_LOG_MIN:g} -> score fijo 100 (baja saturacion espacial)"
    elif factor is not None and factor >= ISC_LOG_MAX:
        regla = f"log10(ISC) >= {ISC_LOG_MAX:g} -> score fijo 10 (alta saturacion espacial)"
    else:
        regla = (
            f"100 - ((log10(ISC) - ({ISC_LOG_MIN:g})) / ({ISC_LOG_MAX:g} - ({ISC_LOG_MIN:g}))) x 90"
        )

    resultado = {
        "competidores_conteo": competidores_conteo,
        "isc": isc,
        "factor_log_isc": round(factor, 4) if factor is not None else None,
        "regla": regla,
        "score": score,
        "aporte_ponderado": round(score * PESO_COMPETENCIA, 1),
        "nota": (
            "El ISC no es el numero de competidores: suma 1/distancia^2 de cada rival. "
            "Dos locales a 50 m penalizan mucho mas que diez a 800 m."
        ),
    }
    resultado["lectura_llana"] = _lectura_llana_competencia(resultado)
    return resultado


def detalle_pilar_trafico(tier: str, afluencia: dict | None, score_traf: float) -> dict[str, Any]:
    afl = afluencia or {}
    medicion_real = tier == "premium" and afl.get("status") == "success"
    if medicion_real:
        saturacion = afl.get("saturación_promedio")
        fuente = "Medición de tráfico peatonal en la zona (promedio diario, %)"
        regla = "Score = promedio de tráfico peatonal medido en la zona (0–100)"
        detalle = f"Promedio de tráfico peatonal: {saturacion}%"
    else:
        fuente = f"Valor estimado para reporte {tier.capitalize()} (sin medición de tráfico peatonal en esta zona)"
        regla = f"Score fijo {SCORE_TRAFICO_SIN_BESTTIME} cuando no hay medición de tráfico peatonal"
        detalle = f"Valor aplicado: {SCORE_TRAFICO_SIN_BESTTIME}"

    resultado = {
        "fuente": fuente,
        "regla": regla,
        "detalle": detalle,
        "score": score_traf,
        "aporte_ponderado": round(score_traf * PESO_TRAFICO, 1),
        "medicion_peatonal_real": medicion_real,
    }
    resultado["lectura_llana"] = _lectura_llana_trafico(resultado, tier)
    return resultado


def desglose_sva_completo(
    analisis: dict,
    *,
    tier: str,
    radio_metros: int,
) -> dict[str, Any]:
    score_dem = float(analisis.get("score_demog", 50.0))
    score_comp = float(analisis.get("score_competencia", 50.0))
    score_traf = float(analisis.get("score_trafico", 50.0))
    sva_ponderado, sva_entero = componer_sva(score_dem, score_comp, score_traf)

    dem = detalle_pilar_demografico(int(analisis.get("poblacion_ponderada", 0)), radio_metros)
    comp = detalle_pilar_competencia(
        float(analisis.get("isc", 0.0)),
        int(analisis.get("competidores_conteo", 0)),
    )
    comp["score"] = score_comp
    comp["aporte_ponderado"] = round(score_comp * PESO_COMPETENCIA, 1)
    traf = detalle_pilar_trafico(tier, analisis.get("afluencia_peatonal"), score_traf)

    return {
        "demografico": dem,
        "competencia": comp,
        "trafico": traf,
        "sva_ponderado": sva_ponderado,
        "sva_entero": sva_entero,
        "sva_reportado": int(analisis.get("sva", sva_entero)),
        "formula_final": (
            f"({score_dem:.1f} x 0.4) + ({score_comp:.1f} x 0.3) + ({score_traf:.1f} x 0.3) "
            f"= {sva_ponderado:.1f} -> redondeo {sva_entero}"
        ),
    }


def escenarios_simulacion_sva(
    analisis: dict,
    *,
    tier: str,
    radio_metros: int,
) -> list[dict[str, Any]]:
    """Escenarios deterministas para el mini simulador del PDF."""
    score_dem = float(analisis.get("score_demog", 50.0))
    score_traf = float(analisis.get("score_trafico", 50.0))
    competidores = list(analisis.get("competidores_listado") or [])
    comp_n = len(competidores) or int(analisis.get("competidores_conteo", 0))
    isc_actual = float(analisis.get("isc", 0.0))
    score_comp_actual = float(analisis.get("score_competencia", calcular_score_competencia(isc_actual)))
    sva_actual = int(analisis.get("sva", componer_sva(score_dem, score_comp_actual, score_traf)[1]))

    def _fila(
        nombre: str,
        n_comp: int,
        isc: float,
        nota: str,
        *,
        es_actual: bool = False,
    ) -> dict[str, Any]:
        if es_actual:
            score_comp = score_comp_actual
            sva_pond, _ = componer_sva(score_dem, score_comp, score_traf)
            sva_int = sva_actual
            delta = 0
        else:
            score_comp = calcular_score_competencia(isc)
            sva_pond, sva_int = componer_sva(score_dem, score_comp, score_traf)
            delta = sva_int - sva_actual
        return {
            "escenario": nombre,
            "competidores": n_comp,
            "isc": isc,
            "score_competencia": score_comp,
            "sva": sva_int,
            "sva_ponderado": sva_pond,
            "delta_vs_actual": delta,
            "nota": nota,
        }

    escenarios: list[dict[str, Any]] = [
        _fila(
            "Situación actual (datos medidos)",
            comp_n,
            isc_actual,
            "Mismos competidores y distancias que el dashboard.",
            es_actual=True,
        )
    ]

    ordenados = sorted(competidores, key=lambda c: float(c.get("distancia_metros") or 99999.0))

    if comp_n >= 2:
        n_mitad = max(1, comp_n // 2)
        isc_mitad = calcular_isc_desde_competidores(ordenados[:n_mitad])
        escenarios.append(
            _fila(
                f"Con {n_mitad} competidores (los más cercanos)",
                n_mitad,
                isc_mitad,
                "Simula retirar los rivales más lejanos; el ISC baja si desaparece presión cercana.",
            )
        )

    # Evita duplicar el escenario de 10 rivales cuando la mitad ya es 10 (p. ej. 20 competidores).
    if comp_n > 10 and comp_n // 2 != 10:
        isc_diez = calcular_isc_desde_competidores(ordenados[:10])
        escenarios.append(
            _fila(
                "Con 10 competidores (los más cercanos)",
                10,
                isc_diez,
                f"Comparación frente a los {comp_n} detectados hoy.",
            )
        )

    if comp_n > 0:
        lista_isc = ordenados if ordenados else competidores
        isc_doble_dist = calcular_isc_distancias_escaladas(lista_isc, factor=2.0)
        escenarios.append(
            _fila(
                "Rivales al doble de distancia (hipotético)",
                comp_n,
                isc_doble_dist,
                "Misma cantidad de competidores, pero cada uno al doble de distancia lineal.",
            )
        )
        escenarios.append(
            _fila(
                "Escenario hipotético: sin rivales en el radio (no es recomendación)",
                0,
                0.0,
                "Contrafactual para ver el techo del pilar de competencia; no implica que debas buscar una zona sin rivales.",
            )
        )

    return escenarios
