"""
Cuestionario guiado de aliados: sugerencias deterministas y validación sin LLM.
"""

from __future__ import annotations

from app.domain.aliados_deterministico import (
    CATEGORIAS_ALIADOS_PERMITIDAS,
    nombre_categoria_places,
    resolver_aliados_por_rubro,
)
from app.schemas.domain.aliados_guiados import (
    ConfiguracionAliadosGuiados,
    ResolucionAliadosGuiados,
    SugerenciaAtractor,
)

PERFILES_VALIDOS = frozenset(
    {
        "publico_general",
        "familias",
        "estudiantes",
        "oficinistas",
        "transporte_publico",
        "compradores_paso",
        "salud_bienestar",
        "adultos_mayores",
    }
)

HORARIOS_VALIDOS = frozenset({"manana", "mediodia", "tarde", "noche_finde"})

ETIQUETAS_PERFIL: dict[str, str] = {
    "publico_general": "Público en general",
    "familias": "Familias con niños",
    "estudiantes": "Estudiantes y jóvenes",
    "oficinistas": "Oficinistas",
    "transporte_publico": "Usuarios de transporte público",
    "compradores_paso": "Compradores de paso",
    "salud_bienestar": "Salud y bienestar",
    "adultos_mayores": "Adultos mayores",
}

ETIQUETAS_HORARIO: dict[str, str] = {
    "manana": "Mañana (6:00–12:00)",
    "mediodia": "Mediodía / comida",
    "tarde": "Tarde / salida de trabajo",
    "noche_finde": "Noche y fin de semana",
}

CATÁLOGO_ATRACTORES: tuple[tuple[str, str], ...] = (
    ("school", "Flujo diario de padres y estudiantes"),
    ("transit_station", "Personas entrando y saliendo todo el día"),
    ("bank", "Empleados y trámites que generan visitas repetidas"),
    ("shopping_mall", "Concentran visitas planeadas de compra"),
    ("supermarket", "Familias en rutina de abastecimiento"),
    ("convenience_store", "Compras rápidas de vecinos y transeúntes"),
    ("park", "Familias y ejercicio en fines de semana"),
    ("doctor", "Visitas por salud y acompañantes"),
    ("restaurant", "Generan flujo de comida (complementan, no sustituyen)"),
    ("cafe", "Punto de reunión y consumo frecuente"),
    ("gym", "Rutina de asistencia varias veces por semana"),
    ("pharmacy", "Visitas cotidianas de salud"),
    ("beauty_salon", "Citas programadas en la zona"),
    ("laundry", "Recurrencia semanal de vecinos"),
)

_BOOST_PERFIL: dict[str, dict[str, int]] = {
    "familias": {"school": 15, "park": 12, "supermarket": 10},
    "estudiantes": {"school": 15, "transit_station": 12, "cafe": 8, "convenience_store": 8},
    "oficinistas": {"bank": 15, "transit_station": 12, "restaurant": 10, "shopping_mall": 8},
    "transporte_publico": {"transit_station": 20, "convenience_store": 12},
    "compradores_paso": {"shopping_mall": 15, "supermarket": 12, "transit_station": 8},
    "salud_bienestar": {"doctor": 15, "pharmacy": 12, "gym": 12},
    "adultos_mayores": {"doctor": 12, "pharmacy": 15, "bank": 10, "supermarket": 8},
}

_BOOST_PUBLICO_GENERAL: dict[str, int] = {
    "transit_station": 10,
    "convenience_store": 8,
    "supermarket": 8,
    "bank": 6,
}

_BOOST_HORARIO: dict[str, dict[str, int]] = {
    "manana": {"school": 12, "bank": 10, "cafe": 8},
    "mediodia": {"restaurant": 12, "supermarket": 10, "bank": 8},
    "tarde": {"transit_station": 12, "school": 10, "shopping_mall": 8, "convenience_store": 8},
    "noche_finde": {"restaurant": 12, "shopping_mall": 10, "park": 8},
}


def _perfiles_especificos(perfiles: list[str]) -> list[str]:
    return [p for p in perfiles if p != "publico_general"]


def _motivo_sugerencia(
    rubro: str,
    tipo: str,
    perfiles: list[str],
    horarios: list[str],
    *,
    solo_publico_general: bool,
) -> str:
    if solo_publico_general:
        if tipo in _BOOST_PUBLICO_GENERAL:
            return "Tráfico mixto en la colonia — transeúntes y vecinos"
        return f"Sugerido por tu giro ({rubro}) — tráfico mixto en la colonia"

    partes_perfil = [ETIQUETAS_PERFIL.get(p, p) for p in _perfiles_especificos(perfiles)]
    partes_horario = [ETIQUETAS_HORARIO.get(h, h) for h in horarios]
    if partes_perfil and partes_horario:
        return f"Relevante para {', '.join(partes_perfil)} y tráfico en {', '.join(partes_horario)}"
    if partes_perfil:
        return f"Relevante para {', '.join(partes_perfil)}"
    if partes_horario:
        return f"Tráfico típico en {', '.join(partes_horario)}"
    return f"Sugerido por tu giro ({rubro})"


def validar_config_guiada(
    config: dict | None,
    *,
    modo: str = "automatico",
) -> ConfiguracionAliadosGuiados:
    if modo != "guiado":
        return {}

    if not config or not isinstance(config, dict):
        raise ValueError("El modo guiado requiere config_aliados_guiados.")

    perfiles = config.get("perfil_cliente") or []
    horarios = config.get("horarios_pico") or []
    confirmados = config.get("atractores_confirmados") or []

    if not isinstance(perfiles, list) or not isinstance(horarios, list) or not isinstance(confirmados, list):
        raise ValueError("config_aliados_guiados debe contener listas válidas.")

    perfiles_limpios = []
    for p in perfiles:
        if p not in PERFILES_VALIDOS:
            raise ValueError(f"Perfil de cliente no válido: {p}")
        if p not in perfiles_limpios:
            perfiles_limpios.append(p)

    if not perfiles_limpios or len(perfiles_limpios) > 3:
        raise ValueError("Selecciona entre 1 y 3 perfiles de cliente.")

    horarios_limpios = []
    for h in horarios:
        if h not in HORARIOS_VALIDOS:
            raise ValueError(f"Horario no válido: {h}")
        if h not in horarios_limpios:
            horarios_limpios.append(h)

    if not horarios_limpios or len(horarios_limpios) > 2:
        raise ValueError("Selecciona entre 1 y 2 horarios pico.")

    confirmados_limpios = []
    for t in confirmados:
        if t not in CATEGORIAS_ALIADOS_PERMITIDAS:
            raise ValueError(f"Tipo de atractor no válido: {t}")
        if t not in confirmados_limpios:
            confirmados_limpios.append(t)

    if len(confirmados_limpios) < 2:
        raise ValueError("Selecciona al menos 2 tipos de lugares que traen gente a tu zona.")
    if len(confirmados_limpios) > 5:
        raise ValueError("El modo guiado permite un máximo de 5 tipos de aliados.")

    return {
        "modo": "guiado",
        "perfil_cliente": perfiles_limpios,
        "horarios_pico": horarios_limpios,
        "atractores_confirmados": confirmados_limpios,
    }


def sugerir_atractores(
    rubro: str,
    *,
    perfil_cliente: list[str] | None = None,
    horarios_pico: list[str] | None = None,
) -> list[SugerenciaAtractor]:
    perfiles = [p for p in (perfil_cliente or []) if p in PERFILES_VALIDOS]
    horarios = [h for h in (horarios_pico or []) if h in HORARIOS_VALIDOS]
    especificos = _perfiles_especificos(perfiles)
    solo_publico = perfiles == ["publico_general"]

    puntajes: dict[str, int] = {}

    matriz = resolver_aliados_por_rubro(rubro)
    for i, tipo in enumerate(matriz):
        puntajes[tipo] = puntajes.get(tipo, 0) + (4 - i) * 10

    if solo_publico:
        for tipo, pts in _BOOST_PUBLICO_GENERAL.items():
            puntajes[tipo] = puntajes.get(tipo, 0) + pts
    else:
        for perfil in especificos:
            for tipo, pts in _BOOST_PERFIL.get(perfil, {}).items():
                puntajes[tipo] = puntajes.get(tipo, 0) + pts

    for horario in horarios:
        for tipo, pts in _BOOST_HORARIO.get(horario, {}).items():
            puntajes[tipo] = puntajes.get(tipo, 0) + pts

    tipos_ordenados = sorted(puntajes.keys(), key=lambda t: (-puntajes[t], t))
    top_sugeridos = {t for t in tipos_ordenados[:4] if puntajes.get(t, 0) > 0}

    visibles: list[str] = []
    for t in matriz:
        if t not in visibles:
            visibles.append(t)
    for t in tipos_ordenados:
        if t not in visibles:
            visibles.append(t)
    for tipo, _ in CATÁLOGO_ATRACTORES:
        if tipo not in visibles:
            visibles.append(tipo)

    resultado: list[SugerenciaAtractor] = []
    for tipo, explicacion in CATÁLOGO_ATRACTORES:
        if tipo not in visibles:
            continue
        pts = puntajes.get(tipo, 0)
        resultado.append(
            {
                "tipo": tipo,
                "etiqueta": nombre_categoria_places(tipo),
                "explicacion": explicacion,
                "motivo": _motivo_sugerencia(rubro, tipo, perfiles, horarios, solo_publico_general=solo_publico),
                "sugerido": tipo in top_sugeridos,
                "puntaje": pts,
            }
        )
    return resultado


def resolver_aliados_guiados(config: ConfiguracionAliadosGuiados, rubro: str) -> ResolucionAliadosGuiados:
    confirmados = list(config.get("atractores_confirmados") or [])
    sugerencias = sugerir_atractores(
        rubro,
        perfil_cliente=config.get("perfil_cliente"),
        horarios_pico=config.get("horarios_pico"),
    )
    return {
        "tipos_busqueda": confirmados,
        "fuente": "guiado_usuario",
        "sugerencias": sugerencias,
        "configuracion": config,
    }


def etiquetas_perfil_legibles(perfiles: list[str] | None) -> str:
    if not perfiles:
        return "No especificado"
    return ", ".join(ETIQUETAS_PERFIL.get(p, p) for p in perfiles)


def etiquetas_horario_legibles(horarios: list[str] | None) -> str:
    if not horarios:
        return "No especificado"
    return ", ".join(ETIQUETAS_HORARIO.get(h, h) for h in horarios)


def etiquetas_atractores_legibles(tipos: list[str] | None) -> str:
    if not tipos:
        return "No especificado"
    return ", ".join(nombre_categoria_places(t) for t in tipos)
