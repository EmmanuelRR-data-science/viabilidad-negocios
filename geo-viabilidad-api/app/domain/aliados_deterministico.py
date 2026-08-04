"""
Matriz determinista rubro → categorías de aliados (atractores de tráfico).
Sin LLM: mismo rubro siempre produce los mismos tipos de Places a consultar.
"""

from __future__ import annotations

import unicodedata

# Categorías válidas en Google Places / panel admin
CATEGORIAS_ALIADOS_PERMITIDAS = frozenset(
    {
        "bank",
        "school",
        "transit_station",
        "supermarket",
        "shopping_mall",
        "convenience_store",
        "park",
        "cafe",
        "restaurant",
        "fast_food",
        "gym",
        "pharmacy",
        "beauty_salon",
        "laundry",
        "doctor",
    }
)

# Clave de matriz → tipos de aliado (máx. 4), ordenados por relevancia geomarketing
_MATRIZ_ALIADOS: dict[str, list[str]] = {
    "cafeteria": ["school", "transit_station", "bank", "shopping_mall"],
    "cafe": ["school", "transit_station", "bank", "shopping_mall"],
    "restaurante": ["transit_station", "shopping_mall", "bank", "park"],
    "comida": ["transit_station", "shopping_mall", "park", "convenience_store"],
    "comida_rapida": ["transit_station", "shopping_mall", "park", "convenience_store"],
    "fast_food": ["transit_station", "shopping_mall", "park", "convenience_store"],
    "gimnasio": ["pharmacy", "supermarket", "beauty_salon", "transit_station"],
    "gym": ["pharmacy", "supermarket", "beauty_salon", "transit_station"],
    "farmacia": ["doctor", "supermarket", "transit_station", "convenience_store"],
    "panaderia": ["supermarket", "school", "transit_station", "cafe"],
    "mascota": ["supermarket", "park", "transit_station", "convenience_store"],
    "estetica": ["shopping_mall", "bank", "transit_station", "gym"],
    "belleza": ["shopping_mall", "bank", "transit_station", "gym"],
    "supermercado": ["bank", "transit_station", "pharmacy", "convenience_store"],
    "abarrotes": ["transit_station", "school", "bank", "convenience_store"],
    "lavanderia": ["transit_station", "supermarket", "bank", "convenience_store"],
    "consultorio": ["pharmacy", "transit_station", "supermarket", "bank"],
    "doctor": ["pharmacy", "transit_station", "supermarket", "bank"],
    "floreria": ["shopping_mall", "school", "doctor", "restaurant"],
    "flor": ["shopping_mall", "school", "doctor", "restaurant"],
}

_ALIADOS_DEFAULT: list[str] = ["transit_station", "school", "bank"]

# Palabras en intenciones que suben prioridad de una categoría (sin añadir tipos nuevos)
_BOOST_INTENCIONES: tuple[tuple[str, str], ...] = (
    ("escuela", "school"),
    ("colegio", "school"),
    ("universidad", "school"),
    ("transporte", "transit_station"),
    ("metro", "transit_station"),
    ("metrobus", "transit_station"),
    ("metrobús", "transit_station"),
    ("parada", "transit_station"),
    ("banco", "bank"),
    ("cajero", "bank"),
    ("plaza comercial", "shopping_mall"),
    ("centro comercial", "shopping_mall"),
    ("supermercado", "supermarket"),
    ("oxxo", "convenience_store"),
    ("farmacia", "pharmacy"),
    ("parque", "park"),
    ("oficina", "bank"),
    ("corporativo", "bank"),
    ("boda", "restaurant"),
    ("bodas", "restaurant"),
    ("evento", "shopping_mall"),
    ("eventos", "shopping_mall"),
    ("graduacion", "school"),
    ("graduación", "school"),
    ("hospital", "doctor"),
    ("clinica", "doctor"),
    ("clínica", "doctor"),
    ("condolencia", "doctor"),
    ("condolencias", "doctor"),
    ("visita", "doctor"),
)


def _normalizar_rubro(texto: str) -> str:
    limpio = unicodedata.normalize("NFKD", str(texto or ""))
    limpio = "".join(ch for ch in limpio if not unicodedata.combining(ch))
    return limpio.lower().strip()


def _clave_matriz_para_rubro(rubro: str) -> str | None:
    texto = _normalizar_rubro(rubro)
    if not texto:
        return None
    # Coincidencia más específica primero (claves más largas)
    for clave in sorted(_MATRIZ_ALIADOS.keys(), key=len, reverse=True):
        if clave in texto:
            return clave
    return None


def _validar_tipos(tipos: list[str]) -> list[str]:
    vistos: set[str] = set()
    resultado: list[str] = []
    for t in tipos:
        if t in CATEGORIAS_ALIADOS_PERMITIDAS and t not in vistos:
            vistos.add(t)
            resultado.append(t)
    return resultado


def _reordenar_por_intenciones(tipos: list[str], intenciones: str | None) -> list[str]:
    if not intenciones or not tipos:
        return tipos
    texto = _normalizar_rubro(intenciones)
    prioridad: list[str] = []
    resto = list(tipos)
    for palabra, categoria in _BOOST_INTENCIONES:
        if palabra in texto and categoria in resto and categoria not in prioridad:
            prioridad.append(categoria)
            resto.remove(categoria)
    return prioridad + resto


def resolver_aliados_por_rubro(rubro: str) -> list[str]:
    """
    Devuelve tipos de Google Places para buscar aliados según matriz cerrada.
    Las intenciones solo reordenan prioridades, nunca agregan categorías nuevas.
    """
    clave = _clave_matriz_para_rubro(rubro)
    base = list(_MATRIZ_ALIADOS.get(clave, _ALIADOS_DEFAULT)) if clave else list(_ALIADOS_DEFAULT)
    tipos = _validar_tipos(base)
    return tipos or list(_ALIADOS_DEFAULT)


# Etiquetas en español para categorías Google Places (tabla IAT, gráficas, FODA).
NOMBRES_CATEGORIAS_PLACES: dict[str, str] = {
    "bank": "Bancos e Instituciones Financieras",
    "school": "Escuelas e Instituciones Educativas",
    "transit_station": "Paradas de Transporte Público",
    "cafe": "Cafeterías",
    "restaurant": "Restaurantes",
    "fast_food": "Comida Rápida",
    "gym": "Gimnasios",
    "pharmacy": "Farmacias",
    "bakery": "Panaderías",
    "beauty_salon": "Estéticas y Salones de Belleza",
    "laundry": "Lavanderías",
    "doctor": "Consultorios Médicos",
    "supermarket": "Supermercados",
    "shopping_mall": "Centros Comerciales",
    "convenience_store": "Abarrotes y Tiendas de Conveniencia",
    "park": "Parques",
    "store": "Tiendas y Comercios",
    "establishment": "Establecimientos Comerciales",
}


def nombre_categoria_places(categoria: str) -> str:
    """Traduce claves internas (bank, shopping_mall) a etiquetas en español."""
    clave = (categoria or "").strip().lower()
    if clave in NOMBRES_CATEGORIAS_PLACES:
        return NOMBRES_CATEGORIAS_PLACES[clave]
    return categoria.replace("_", " ").strip().title() if categoria else "Categoría"


def etiquetas_aliados_legibles(tipos: list[str]) -> str:
    return ", ".join(nombre_categoria_places(t) for t in tipos)
