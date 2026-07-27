"""Filtro semántico de competidores por giro/rubro.

Migrado desde clients/google_places.py → clients/v0/google/ para cumplir
la política de hot-path v0-only.
"""

from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger("google_giro_filter")

_STOPWORDS_GIRO = frozenset(
    {
        "para",
        "de",
        "del",
        "la",
        "el",
        "los",
        "las",
        "y",
        "o",
        "en",
        "un",
        "una",
        "con",
        "sin",
        "otro",
        "otra",
        "negocio",
        "tienda",
        "local",
        "venta",
        "servicio",
        "comercial",
        "centro",
        "mexico",
        "cdmx",
    }
)

_DOMINIO_GIRO: dict[str, dict[str, list[str]]] = {
    "mascota": {
        "anchors": [
            "mascota",
            "mascotas",
            "perro",
            "perros",
            "gato",
            "gatos",
            "pet",
            "canino",
            "veterin",
            "accesorio",
            "accesorios",
            "alimento",
            "pecera",
        ],
        "relacionados": [
            "mascota",
            "perro",
            "gato",
            "canino",
            "felino",
            "pet",
            "collar",
            "correa",
            "arena",
            "alimento",
            "veterin",
            "peluquer",
            "estetica canina",
            "estética canina",
            "accesorio",
            "juguete",
            "croqueta",
            "snack",
            "hueso",
            "placa",
        ],
        "conflictos": [
            "acuario",
            "peces",
            "pez",
            "marino",
            "coral",
            "reef",
            "acuatico",
            "acuático",
            "tanque",
            "filtracion",
            "filtración",
            "buceo",
            "snorkel",
            "acuicultura",
        ],
    },
    "cafeteria": {
        "anchors": ["cafeteria", "cafetería", "cafe", "café", "coffee", "bebida", "soda"],
        "relacionados": ["café", "cafe", "coffee", "espresso", "latte", "capuchino", "bebida", "postre", "pan"],
        "conflictos": ["gimnasio", "farmacia", "consultorio", "hospital", "taller mecanico", "lavanderia"],
    },
    "restaurante": {
        "anchors": ["restaurante", "comida", "cocina", "menu", "menú", "gastronom"],
        "relacionados": [
            "restaurante",
            "comida",
            "platillo",
            "menu",
            "menú",
            "cocina",
            "chef",
            "mesa",
            "servicio",
            "cena",
            "banderilla",
            "banderillas",
            "antojo",
            "antojito",
            "taco",
            "tacos",
            "torta",
            "mariscos",
            "fonda",
        ],
        "conflictos": ["gimnasio", "farmacia", "consultorio", "escuela", "taller"],
    },
    "farmacia": {
        "anchors": ["farmacia", "medicamento", "pharmacy", "botica"],
        "relacionados": ["farmacia", "medicamento", "receta", "botica", "salud", "vitamina", "analgesico"],
        "conflictos": ["restaurante", "cafeteria", "gimnasio", "escuela", "ropa"],
    },
    "gimnasio": {
        "anchors": ["gimnasio", "gym", "fitness", "entrenamiento", "crossfit"],
        "relacionados": ["gimnasio", "gym", "fitness", "entrenamiento", "pesas", "cardio", "clase"],
        "conflictos": ["farmacia", "restaurante", "cafeteria", "escuela", "consultorio"],
    },
    "estetica": {
        "anchors": ["estetica", "estética", "belleza", "salon", "salón", "spa", "uñas", "cabello"],
        "relacionados": ["estetica", "estética", "belleza", "corte", "uñas", "peinado", "spa", "facial"],
        "conflictos": ["gimnasio", "farmacia", "restaurante", "escuela", "taller"],
    },
    "floreria": {
        "anchors": ["floreria", "florería", "flor", "flores", "floral", "ramo", "arreglo"],
        "relacionados": [
            "flor",
            "flores",
            "floral",
            "floreria",
            "florería",
            "ramo",
            "arreglo",
            "bouquet",
            "corona",
            "detalle",
            "regalo",
            "planta",
            "plantas",
        ],
        "conflictos": [
            "supermercado",
            "comer",
            "restaurante",
            "cafeteria",
            "cafetería",
            "cafe",
            "café",
            "vidrio",
            "ropa",
            "parisina",
            "market",
            "abarrotes",
        ],
    },
}

_TIPOS_GOOGLE_COMIDA = frozenset({"restaurant", "meal_takeaway", "meal_delivery", "cafe", "bakery", "food", "bar"})


def _google_types_competidor(competidor: dict) -> set[str]:
    raw = competidor.get("google_types") or []
    return {str(t).lower() for t in raw}


def _confia_tipo_google_para_dominio(dominio: str, competidor: dict) -> bool:
    if dominio != "restaurante":
        return False
    return bool(_google_types_competidor(competidor) & _TIPOS_GOOGLE_COMIDA)


def _normalizar_texto_giro(texto: str) -> str:
    limpio = unicodedata.normalize("NFKD", str(texto or ""))
    limpio = "".join(ch for ch in limpio if not unicodedata.combining(ch))
    limpio = limpio.lower()
    limpio = re.sub(r"[^a-z0-9áéíóúñü\s]", " ", limpio)
    return re.sub(r"\s+", " ", limpio).strip()


def _detectar_dominios_rubro(rubro: str) -> list[str]:
    texto = _normalizar_texto_giro(rubro)
    dominios = [dom for dom, cfg in _DOMINIO_GIRO.items() if any(a in texto for a in cfg["anchors"])]
    return dominios or ["_generico"]


def _texto_evaluable_competidor(competidor: dict) -> tuple[str, str, str]:
    nombre = _normalizar_texto_giro(competidor.get("nombre", ""))
    tipo = _normalizar_texto_giro(competidor.get("tipo", ""))
    reseñas = _normalizar_texto_giro(" ".join(rev.get("texto", "") for rev in (competidor.get("reseñas_google") or [])))
    return nombre, tipo, reseñas


def _contiene_termino(texto: str, termino: str) -> bool:
    if not texto or not termino:
        return False
    if re.search(rf"\b{re.escape(termino)}", texto):
        return True
    if len(termino) >= 4 and termino in texto.replace(" ", ""):
        return True
    return False


def _contar_terminos(texto: str, terminos: list[str]) -> int:
    return sum(1 for t in terminos if _contiene_termino(texto, t))


def _tokens_rubro_generico(rubro: str) -> list[str]:
    texto = _normalizar_texto_giro(rubro.split(".")[0])
    tokens = [t for t in texto.split() if len(t) > 3 and t not in _STOPWORDS_GIRO]
    variantes: list[str] = []
    for t in tokens:
        variantes.append(t)
        if t.startswith("florer") or t == "flor":
            variantes.extend(["flor", "flores", "floral", "floreria"])
    vistos: set[str] = set()
    resultado: list[str] = []
    for v in variantes:
        if v not in vistos:
            vistos.add(v)
            resultado.append(v)
    return resultado


def competidor_es_relevante_al_giro(rubro: str, competidor: dict) -> bool:
    """True si el nombre/tipo/reseñas del competidor son coherentes con el rubro."""
    nombre, tipo, reseñas = _texto_evaluable_competidor(competidor)
    if not nombre and not tipo and not reseñas:
        return True

    tiene_reseñas = bool(reseñas)
    texto_relacion = f"{nombre} {reseñas}".strip() if tiene_reseñas else f"{nombre} {tipo}".strip()
    texto_conflicto = f"{nombre} {reseñas}".strip()

    dominios = _detectar_dominios_rubro(rubro)

    for dominio in dominios:
        if dominio == "_generico":
            tokens = _tokens_rubro_generico(rubro)
            if not tokens:
                return True
            hits = sum(1 for t in tokens if _contiene_termino(texto_relacion, t))
            return hits > 0

        if _confia_tipo_google_para_dominio(dominio, competidor):
            return True

        cfg = _DOMINIO_GIRO[dominio]
        rel = _contar_terminos(texto_relacion, cfg["relacionados"])
        conf = _contar_terminos(texto_conflicto, cfg["conflictos"])

        if conf >= 2 and rel == 0:
            return False
        if conf >= 1 and rel == 0:
            if tiene_reseñas:
                return False
            if _contar_terminos(nombre, cfg["conflictos"]) >= 1:
                return False

        return rel >= 1

    return True


def filtrar_competidores_por_giro(rubro: str, competidores: list[dict]) -> list[dict]:
    """Conserva solo competidores alineados al rubro según nombre, tipo y reseñas."""
    filtrados: list[dict] = []
    for comp in competidores:
        if competidor_es_relevante_al_giro(rubro, comp):
            comp["giro_relevante"] = True
            filtrados.append(comp)
        else:
            comp["giro_relevante"] = False
            logger.info(
                "Competidor descartado por desalineación de giro '%s': %s",
                rubro,
                comp.get("nombre", "?"),
            )
    return filtrados
