import logging
import re
import unicodedata

import requests

from app.config import GOOGLE_MAPS_API_KEY

logger = logging.getLogger("google_places")

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

# Dominios semánticos: anclas en el rubro, términos afines y giros conflictivos en reseñas/nombre.
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
        "relacionados": ["comida", "platillo", "menu", "menú", "cocina", "chef", "mesa", "servicio", "cena"],
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
}


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
    """Nombre, tipo comercial asignado y texto de reseñas (normalizados)."""
    nombre = _normalizar_texto_giro(competidor.get("nombre", ""))
    tipo = _normalizar_texto_giro(competidor.get("tipo", ""))
    reseñas = _normalizar_texto_giro(
        " ".join(rev.get("texto", "") for rev in (competidor.get("reseñas_google") or []))
    )
    return nombre, tipo, reseñas


def _contiene_termino(texto: str, termino: str) -> bool:
    if not texto or not termino:
        return False
    return bool(re.search(rf"\b{re.escape(termino)}", texto))


def _contar_terminos(texto: str, terminos: list[str]) -> int:
    return sum(1 for t in terminos if _contiene_termino(texto, t))


def _tokens_rubro_generico(rubro: str) -> list[str]:
    return [
        t
        for t in _normalizar_texto_giro(rubro).split()
        if len(t) > 3 and t not in _STOPWORDS_GIRO
    ]


def competidor_es_relevante_al_giro(rubro: str, competidor: dict) -> bool:
    """
    True si el nombre/tipo/reseñas del competidor son coherentes con el rubro analizado.
    Excluye casos como acuarios indexados por la palabra «mascotas» en Google Places.
    """
    nombre, tipo, reseñas = _texto_evaluable_competidor(competidor)
    if not nombre and not tipo and not reseñas:
        return True

    tiene_reseñas = bool(reseñas)
    # Con reseñas: el tipo asignado por Google suele ser genérico y no debe anular el contenido real.
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

_MOCK_RESEÑAS = [
    "Buen servicio en general, aunque los tiempos de espera suben en horario pico.",
    "Precios algo elevados para la zona, pero la atención al cliente es amable.",
    "Ubicación conveniente; el local se siente saturado los fines de semana.",
    "Productos de calidad aceptable; podrían mejorar la limpieza del espacio.",
]


def _google_api_disponible() -> bool:
    return bool(
        GOOGLE_MAPS_API_KEY
        and not GOOGLE_MAPS_API_KEY.startswith("pega_tu")
        and "tu_token" not in GOOGLE_MAPS_API_KEY
    )


def _truncar_texto(texto: str, *, max_len: int = 220) -> str:
    limpio = " ".join(str(texto or "").split())
    if len(limpio) <= max_len:
        return limpio
    return limpio[: max_len - 1].rstrip() + "…"


def obtener_reseñas_lugar(place_id: str, *, max_reseñas: int = 3) -> list[dict]:
    """
    Obtiene reseñas públicas de Google Maps para un place_id.
    Retorna lista de dicts: texto, rating, autor, fecha_relativa.
    """
    if not place_id:
        return []

    if not _google_api_disponible():
        return [
            {
                "texto": _MOCK_RESEÑAS[i % len(_MOCK_RESEÑAS)],
                "rating": 4 - (i % 2),
                "autor": f"Cliente Google {i + 1}",
                "fecha_relativa": f"hace {i + 1} meses",
            }
            for i in range(min(max_reseñas, 2))
        ]

    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "reviews",
        "language": "es",
        "key": GOOGLE_MAPS_API_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "OK":
            logger.warning("Place Details sin reseñas para %s: %s", place_id, data.get("status"))
            return []

        reseñas: list[dict] = []
        for item in data.get("result", {}).get("reviews", [])[:max_reseñas]:
            texto = _truncar_texto(item.get("text", ""))
            if not texto:
                continue
            reseñas.append(
                {
                    "texto": texto,
                    "rating": int(item.get("rating") or 0),
                    "autor": str(item.get("author_name") or "Usuario de Google"),
                    "fecha_relativa": str(item.get("relative_time_description") or ""),
                }
            )
        return reseñas
    except Exception as err:
        logger.error("Error al obtener reseñas de Google para %s: %s", place_id, err)
        return []


def enriquecer_competidores_con_reseñas(
    competidores: list[dict],
    *,
    min_resenas: int = 5,
    max_reseñas_por_competidor: int = 2,
) -> None:
    """Agrega reseñas_google a los competidores destacados (mutación in-place)."""
    for comp in competidores:
        if int(comp.get("user_ratings_total") or 0) < min_resenas:
            comp["reseñas_google"] = []
            continue
        if comp.get("reseñas_google"):
            continue
        comp["reseñas_google"] = obtener_reseñas_lugar(
            comp.get("place_id"),
            max_reseñas=max_reseñas_por_competidor,
        )


def obtener_direccion(lat: float, lng: float) -> dict:
    """
    Realiza geocodificación inversa mediante la API de Google Geocoding para resolver
    una latitud y longitud en una dirección mexicana estructurada.
    """
    # Si no hay API key de Google o es una clave de prueba
    if not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY.startswith("pega_tu") or "tu_token" in GOOGLE_MAPS_API_KEY:
        logger.info(f"Modo Desarrollo (Simulado): Devolviendo dirección mexicana ficticia para ({lat}, {lng}).")
        return {
            "calle": "Plaza de la Constitución",
            "numero": "S/N",
            "colonia": "Centro Histórico de la Cdad. de México",
            "codigo_postal": "06000",
            "localidad": "Ciudad de México",
            "municipio": "Cuauhtémoc",
            "estado": "Ciudad de México",
            "pais": "México",
            "formato_completo": "Plaza de la Constitución S/N, Centro Histórico de la Cdad. de México, 06000 Cuauhtémoc, CDMX, México",
        }

    # Llamada real a la API de Google Geocoding
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"latlng": f"{lat},{lng}", "key": GOOGLE_MAPS_API_KEY, "language": "es"}

    try:
        logger.info(f"Consultando Google Geocoding para coordenadas: ({lat}, {lng})...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "OK" and data.get("results"):
            result = data["results"][0]
            components = result.get("address_components", [])

            # Inicializar campos vacíos
            calle = ""
            numero = ""
            colonia = ""
            cp = ""
            localidad = ""
            municipio = ""
            estado = ""
            pais = ""

            # Iterar y mapear componentes según el estándar de Google
            for comp in components:
                types = comp.get("types", [])
                long_name = comp.get("long_name", "")

                if "route" in types:
                    calle = long_name
                elif "street_number" in types:
                    numero = long_name
                elif "sublocality_level_1" in types or "political" in types and "sublocality" in types:
                    colonia = long_name
                elif "postal_code" in types:
                    cp = long_name
                elif "locality" in types:
                    localidad = long_name
                elif "administrative_area_level_2" in types:
                    municipio = long_name
                elif "administrative_area_level_1" in types:
                    estado = long_name
                elif "country" in types:
                    pais = long_name

            # Fallback en caso de que colonia o localidad queden vacíos
            if not colonia:
                # Buscar neighborhood
                for comp in components:
                    if "neighborhood" in comp.get("types", []):
                        colonia = comp.get("long_name", "")
                        break

            return {
                "calle": calle or "Calle no especificada",
                "numero": numero or "S/N",
                "colonia": colonia or "Colonia no detectada",
                "codigo_postal": cp or "00000",
                "localidad": localidad or municipio or estado,
                "municipio": municipio or "Municipio no especificado",
                "estado": estado or "Estado no especificado",
                "pais": pais or "México",
                "formato_completo": result.get("formatted_address", "Dirección no estructurada"),
            }
        else:
            status_err = data.get("status", "UNKNOWN_ERROR")
            logger.error(f"Google Geocoding no retornó resultados válidos. Status: {status_err}")
            raise Exception(f"Google Geocoding falló con estatus: {status_err}")

    except Exception as e:
        logger.error(f"Error en llamada a Google Geocoding API: {e}")
        # Propagar error que el middleware de excepciones amigables se encargará de traducir
        raise e


def buscar_competidores(lat: float, lng: float, radio: float, google_type: str, keyword: str | None = None) -> list:
    """
    Consume la API de Google Places Nearby Search para localizar los comercios
    en un radio de distancia clasificados bajo el tipo específico de Google.
    """
    if not _google_api_disponible():
        logger.info(
            f"Modo Desarrollo (Simulado): Retornando lista de competidores simulados para tipo: {google_type}, keyword: {keyword}."
        )
        display_name = keyword.capitalize() if keyword else google_type.capitalize()
        # Generar competidores ficticios y realistas
        return [
            {
                "place_id": f"plc_mock_10{i}",
                "nombre": f"Competidor {display_name} Simulado {i + 1}",
                "latitud": lat + (0.001 * (i + 1) * (-1 if i % 2 == 0 else 1)),
                "longitud": lng + (0.001 * (i + 2) * (1 if i % 2 == 0 else -1)),
                "direccion": f"Av. Principal #{100 * (i + 1)}, Colonia Centro",
                "rating": round(3.5 + (0.2 * i), 1),
                "user_ratings_total": 10 * (i + 3),
            }
            for i in range(4)
        ]

    # Llamada real a Google Places Nearby Search
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {"location": f"{lat},{lng}", "radius": radio, "type": google_type, "key": GOOGLE_MAPS_API_KEY}
    if keyword:
        params["keyword"] = keyword

    try:
        logger.info(
            f"Buscando competidores cercanos '{google_type}' con palabra clave '{keyword}' en radio {radio}m..."
        )
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Tipos genéricos donde no aplica el filtro estricto de categoría
        tipos_genericos = {"establishment", "store", "point_of_interest"}

        competidores = []
        descartados = 0
        if data.get("status") in ["OK", "ZERO_RESULTS"]:
            for item in data.get("results", []):
                # Filtro de relevancia: Google a veces devuelve negocios mal categorizados
                # (ej. una clínica como 'fast_food'). Si pedimos un tipo específico sin keyword,
                # el resultado DEBE declarar ese tipo en su clasificación oficial.
                item_types = item.get("types", [])
                if not keyword and google_type not in tipos_genericos and item_types and google_type not in item_types:
                    descartados += 1
                    continue

                loc = item.get("geometry", {}).get("location", {})
                competidores.append(
                    {
                        "place_id": item.get("place_id"),
                        "nombre": item.get("name"),
                        "latitud": loc.get("lat"),
                        "longitud": loc.get("lng"),
                        "direccion": item.get("vicinity", "Dirección no disponible"),
                        "rating": item.get("rating", 0.0),
                        "user_ratings_total": item.get("user_ratings_total", 0),
                    }
                )
            if descartados:
                logger.info(
                    f"Filtro de relevancia Places: {descartados} resultado(s) descartado(s) por no declarar "
                    f"el tipo '{google_type}' en su clasificación oficial."
                )
            return competidores
        else:
            status_err = data.get("status", "UNKNOWN_ERROR")
            logger.error(f"Google Places Nearby Search falló. Status: {status_err}")
            raise Exception(f"Google Places Nearby Search falló con estatus: {status_err}")

    except Exception as e:
        logger.error(f"Error en llamada a Google Places Nearby Search: {e}")
        raise e


def obtener_mapa_estatico(
    lat: float,
    lng: float,
    radio: int,
    competidores: list,
    aliados: list | None = None,
    *,
    incluir_aliados: bool = False,
) -> bytes:
    """
    Fallback: Google Static Maps en alta resolución (scale=2) con pines azul/rojo/verde.
    """
    if not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY.startswith("pega_tu") or "tu_token" in GOOGLE_MAPS_API_KEY:
        logger.info("Modo Desarrollo (Simulado): Evitando llamada a Google Static Maps. Retornando None.")
        return None

    url = "https://maps.googleapis.com/maps/api/staticmap"

    # Determinar zoom según el radio (metros)
    zoom = 14
    if radio <= 500:
        zoom = 15
    elif radio <= 1000:
        zoom = 14
    elif radio <= 3000:
        zoom = 13
    else:
        zoom = 12

    markers = [f"color:blue|label:O|{lat},{lng}"]

    comp_added = 0
    for comp in competidores:
        if comp_added >= 15:
            break
        c_lat = comp.get("latitud")
        c_lng = comp.get("longitud")
        if c_lat and c_lng:
            markers.append(f"color:red|{c_lat},{c_lng}")
            comp_added += 1

    if incluir_aliados and aliados:
        ally_added = 0
        for aliado in aliados:
            if ally_added >= 25:
                break
            a_lat = aliado.get("latitud")
            a_lng = aliado.get("longitud")
            if a_lat and a_lng:
                markers.append(f"color:green|{a_lat},{a_lng}")
                ally_added += 1

    marker_query = "&".join([f"markers={m}" for m in markers])
    style_query = "style=feature:poi.business|visibility:off"
    full_url = (
        f"{url}?center={lat},{lng}&zoom={zoom}&size=640x400&scale=2&maptype=roadmap"
        f"&key={GOOGLE_MAPS_API_KEY}&{style_query}&{marker_query}"
    )

    try:
        logger.info(f"Consultando Google Static Maps para coordenadas ({lat}, {lng})...")
        response = requests.get(full_url, timeout=15)
        response.raise_for_status()
        logger.info("Mapa estático recuperado con éxito desde Google Maps.")
        return response.content
    except Exception as e:
        logger.error(f"Error al obtener mapa estático de Google: {e}")
        return None


def buscar_coordenadas_por_direccion(direccion: str) -> list[dict]:
    """
    Realiza geocodificación directa mediante la API de Google Geocoding para resolver
    una dirección de texto en una latitud, longitud y dirección formateada en México.
    """
    if not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY.startswith("pega_tu") or "tu_token" in GOOGLE_MAPS_API_KEY:
        logger.info(f"Modo Desarrollo (Simulado): Devolviendo geocodificación simulada para query: '{direccion}'.")
        # Devolver resultados simulados realistas para facilitar pruebas y desarrollo
        return [
            {
                "direccion": f"{direccion}, Ciudad de México, México",
                "latitud": 19.432608,
                "longitud": -99.133208,
            },
            {
                "direccion": f"Av. Benito Juárez, {direccion}, Guadalajara, Jal., México",
                "latitud": 20.659698,
                "longitud": -103.349609,
            },
        ]

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": direccion,
        "key": GOOGLE_MAPS_API_KEY,
        "language": "es",
        "components": "country:MX",  # Forzar que la búsqueda ocurra en México
    }

    try:
        logger.info(f"Consultando Google Geocoding (Directo) para dirección: '{direccion}'...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        resultados = []
        if data.get("status") == "OK" and data.get("results"):
            for result in data["results"]:
                loc = result.get("geometry", {}).get("location", {})
                resultados.append(
                    {
                        "direccion": result.get("formatted_address"),
                        "latitud": loc.get("lat"),
                        "longitud": loc.get("lng"),
                    }
                )
        return resultados
    except Exception as e:
        logger.error(f"Error en llamada a Google Geocoding (Directo): {e}")
        raise e
