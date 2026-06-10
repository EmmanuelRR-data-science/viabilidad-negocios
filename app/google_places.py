import logging

import requests

from app.config import GOOGLE_MAPS_API_KEY

logger = logging.getLogger("google_places")


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
    if not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY.startswith("pega_tu") or "tu_token" in GOOGLE_MAPS_API_KEY:
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
