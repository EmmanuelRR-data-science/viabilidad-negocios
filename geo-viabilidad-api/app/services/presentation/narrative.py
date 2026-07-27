"""
Textos enriquecidos para la lectura estratégica del PDF (sección 1 y 5) y resumen metodológico.
Sin LLM: derivados de métricas ya calculadas.
"""

from __future__ import annotations


def _interpretar_nse_comercial(etiqueta: str) -> str:
    et = (etiqueta or "").upper()
    if "A/B" in et or et.startswith("A"):
        return (
            "Perfil compatible con ticket medio-alto, productos de especialidad y mayor sensibilidad "
            "a calidad y experiencia que a precio mínimo."
        )
    if "C+" in et or "MEDIO ALTO" in et:
        return "Perfil de consumo mixto: acepta propuestas de valor claras con precios competitivos y buen servicio."
    if "C" in et and "C-" not in et:
        return "Mercado de volumen moderado: conviene equilibrar precio, conveniencia y cercanía."
    if "D" in et or "E" in et:
        return (
            "Mercado sensible al precio y a la conveniencia cotidiana; el ticket debe ser accesible "
            "y la propuesta muy clara."
        )
    return "Usa el NSE como referencia de poder adquisitivo relativo en el radio, no como etiqueta del cliente final."


def enriquecer_item_lectura(texto: str, analisis: dict) -> str:
    """Expande bullets telegráficos (p. ej. NSE + escolaridad) con contexto comercial."""
    t = (texto or "").strip()
    if not t:
        return t
    if len(t) >= 160 and "escolaridad" not in t.lower() and "nse" not in t.lower():
        return t

    nse = analisis.get("nse") or {}
    metricas = nse.get("metricas") or {}
    etiq = nse.get("nse_etiqueta", "No disponible")
    esc = float(metricas.get("escolaridad_promedio", 0) or 0)
    net = float(metricas.get("internet_pct", 0) or 0)
    autos = float(metricas.get("autos_pct", 0) or 0)
    tl = t.lower()

    if "nse" in tl or "escolaridad" in tl or "socioecon" in tl:
        return (
            f"El mercado residente en el radio se clasifica como {etiq}. "
            f"La escolaridad promedio equivale a {esc:.1f} años de estudio; "
            f"{net:.1f}% de los hogares reportan internet y {autos:.1f}% cuentan con automóvil. "
            f"{_interpretar_nse_comercial(etiq)}"
        )

    if "densidad" in tl or "hab/km" in tl or "población" in tl or "poblacion" in tl:
        pob = int(analisis.get("poblacion_ponderada", 0))
        dens = float(analisis.get("densidad_hab_km2", 0))
        return (
            f"En el radio analizado residen {pob:,} personas con densidad de {dens:,.1f} hab/km². "
            f"Esto define el tamaño del mercado cautivo a pie o en rutina diaria, no el flujo de visitantes."
        )

    if "competidor" in tl or "saturación" in tl or "saturacion" in tl:
        n = int(analisis.get("competidores_conteo", 0))
        if n == 0:
            return (
                "No se detectaron competidores directos del giro en el radio contratado; "
                "eso facilita la entrada, pero conviene validar si el giro está subrepresentado en Google Places."
            )
        return (
            f"Se contabilizaron {n} establecimientos competidores en el radio. "
            f"El SVA no solo cuenta cuántos son, sino qué tan cerca están: rivales muy próximos "
            f"presionan más el score que muchos rivales lejanos."
        )

    if "atractor" in tl or "aliado" in tl or "índice de atractores" in tl:
        conteos = {k: v for k, v in (analisis.get("aliados_conteos") or {}).items() if k != "ia_auto"}
        total = sum(conteos.values())
        if total > 0:
            return (
                f"Hay {total} puntos de interés complementarios en {len(conteos)} categorías "
                f"(escuelas, transporte, comercios, etc.). Generan flujo de personas que podrían "
                f"acercarse a tu local si la propuesta encaja con sus rutinas."
            )

    if "afluencia" in tl or "peatonal" in tl:
        afl = analisis.get("afluencia_peatonal") or {}
        if afl.get("status") == "success":
            return (
                f"La telemetría peatonal identifica mayor actividad el {afl.get('dia_pico', 'N/D')} "
                f"alrededor de las {afl.get('hora_pico', 'N/D')}. Alinea horarios y promociones a esos picos."
            )
        return (
            "No hubo medición de tráfico peatonal en esta coordenada; el pilar usa un valor "
            "base. Valida en sitio los horarios de mayor paso antes de definir operación."
        )

    return t


def enriquecer_lista_lectura(items: list[str] | None, analisis: dict, *, max_items: int = 3) -> list[str]:
    resultado: list[str] = []
    for raw in items or []:
        texto = enriquecer_item_lectura(str(raw).strip(), analisis)
        if texto and texto not in resultado:
            resultado.append(texto)
        if len(resultado) >= max_items:
            break
    return resultado


def _condiciones_mejora_sva(analisis: dict, *, tier: str, radio_metros: int) -> list[str]:
    from app.domain.sva_calculo import desglose_sva_completo

    desglose = desglose_sva_completo(analisis, tier=tier, radio_metros=radio_metros)
    dem = desglose["demografico"]
    comp = desglose["competencia"]
    traf = desglose["trafico"]
    sugerencias: list[str] = []

    if float(dem["score"]) < 70:
        sugerencias.append(
            "Demografía: un radio mayor o una zona con mayor densidad residencial elevaría el pilar "
            f"(hoy {dem['score']:.0f}/100). Evalúa si un punto a pocos metros mejora la captación."
        )
    if float(comp["score"]) < 70:
        sugerencias.append(
            "Competencia: diferenciación clara (nicho, horario, servicio) es clave cuando el pilar "
            f"está en {comp['score']:.0f}/100; el simulador SVA muestra cuánto cambiaría el score "
            "si los rivales estuvieran más lejos."
        )
    if float(traf["score"]) < 65:
        sugerencias.append(
            "Tráfico peatonal: ubicarse más cerca de atractores (transporte, escuelas, plazas) o validar "
            f"paso de personas en campo puede mejorar el pilar ({traf['score']:.0f}/100)."
        )
    if not sugerencias:
        sugerencias.append(
            "Mantén la propuesta de valor enfocada en el perfil NSE del radio y monitorea que nuevos "
            "competidores muy cercanos no erosionen la ventaja actual."
        )
    return sugerencias[:3]


def _negrita(texto: str, *, html: bool) -> str:
    return f"<b>{texto}</b>" if html else texto


def generar_conclusion_detallada(
    analisis: dict,
    rubro: str,
    *,
    tier: str,
    radio_metros: int,
    html: bool = False,
) -> str:
    """Párrafo ejecutivo: por qué el SVA, factores y cómo mejorarlo."""
    from app.domain.sva_calculo import desglose_sva_completo

    sva = int(analisis.get("sva", 0))
    desglose = desglose_sva_completo(analisis, tier=tier, radio_metros=radio_metros)
    dem = desglose["demografico"]
    comp = desglose["competencia"]
    traf = desglose["trafico"]
    competencia = int(analisis.get("competidores_conteo", 0))
    nse_etiq = (analisis.get("nse") or {}).get("nse_etiqueta", "No disponible")

    if sva >= 80:
        veredicto = "la viabilidad comercial es favorable"
    elif sva >= 50:
        veredicto = "la viabilidad es moderada y exige diferenciación"
    else:
        veredicto = "la viabilidad es limitada y el riesgo operativo es elevado"

    mejoras = _condiciones_mejora_sva(analisis, tier=tier, radio_metros=radio_metros)
    mejora_txt = " ".join(f"({i + 1}) {m}" for i, m in enumerate(mejoras))
    score_dem = f"{dem['score']:.0f}/100"
    score_comp = f"{comp['score']:.0f}/100"
    score_traf = f"{traf['score']:.0f}/100"

    return (
        f"Obtuviste un {_negrita(f'Score de Viabilidad (SVA) de {sva}/100', html=html)}, por lo que {veredicto} "
        f"para el giro {_negrita(rubro, html=html)} en un radio de {radio_metros:,} m. "
        f"El resultado no es una opinión: suma tres pilares con pesos fijos — "
        f"demografía {_negrita(score_dem, html=html)} (40%), "
        f"competencia {_negrita(score_comp, html=html)} (30%) con {competencia} rivales medidos, "
        f"y tráfico peatonal {_negrita(score_traf, html=html)} (30%). "
        f"El mercado residente se perfila como {_negrita(nse_etiq, html=html)}. "
        f"{dem.get('lectura_llana', '')} {comp.get('lectura_llana', '')} {traf.get('lectura_llana', '')} "
        f"{_negrita('Para mejorar o defender el score:', html=html)} {mejora_txt}"
    )


def bloques_metodologia_resumen(
    analisis: dict,
    *,
    tier: str,
    radio_metros: int,
) -> list[tuple[str, str]]:
    """Encabezado + párrafo para la sección 6 (resumen de metodología y glosarios)."""
    from app.domain.sva_calculo import DENSIDAD_MINIMA_HAB_KM2, DENSIDAD_OPTIMA_HAB_KM2, desglose_sva_completo

    desglose = desglose_sva_completo(analisis, tier=tier, radio_metros=radio_metros)
    bloques: list[tuple[str, str]] = []

    bloques.append(
        (
            "Score SVA (resumen)",
            "Métrica compuesta 0–100: demografía 40%, competencia 30%, tráfico peatonal 30%. "
            "El desglose por pilar y el glosario están en el apartado anterior de esta sección.",
        )
    )
    bloques.append(
        (
            "Pilar demográfico",
            f"Usa densidad en el radio (hab/km²), no población municipal. "
            f"Umbrales calibrados: ≤{DENSIDAD_MINIMA_HAB_KM2:,.0f} hab/km² mercado disperso; "
            f"≥{DENSIDAD_OPTIMA_HAB_KM2:,.0f} hab/km² demanda sólida; entre ambos, escala logarítmica.",
        )
    )
    bloques.append(
        (
            "Población INEGI (AGEBs)",
            "La población se estima intersectando el círculo del radio con polígonos AGEB urbanos "
            "del Censo 2020. Solo se pondera la fracción de cada AGEB dentro del radio.",
        )
    )
    bloques.append(
        (
            "Competencia y tráfico peatonal",
            f"{desglose['competencia'].get('nota', '')} "
            f"Fuente del pilar tráfico peatonal: {desglose['trafico'].get('fuente', 'N/D')}.",
        )
    )
    nse = analisis.get("nse") or {}
    if nse.get("nse_etiqueta"):
        m = nse.get("metricas") or {}
        bloques.append(
            (
                "Nivel socioeconómico (NSE)",
                f"Estimación AMAI a partir de escolaridad, internet y equipamiento del hogar "
                f"en AGEBs del radio (fuente: {m.get('fuente', 'censo')}). "
                f"Etiqueta en este punto: {nse.get('nse_etiqueta')}.",
            )
        )
    return bloques
