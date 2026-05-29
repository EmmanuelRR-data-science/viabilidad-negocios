import logging

import requests

from app.config import DEV_MODE, GOOGLE_MAPS_API_KEY

logger = logging.getLogger("google_places")


def obtener_direccion(lat: float, lng: float) -> dict:
    """
    Realiza geocodificación inversa mediante la API de Google Geocoding para resolver
    una latitud y longitud en una dirección mexicana estructurada.
    """
    # Si estamos en modo de desarrollo o no hay API key de Google
    if DEV_MODE or not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY.startswith("pega_tu"):
        logger.info(f"Modo Desarrollo: Devolviendo dirección mexicana simulada para ({lat}, {lng}).")
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


def buscar_competidores(lat: float, lng: float, radio: float, google_type: str) -> list:
    """
    Consume la API de Google Places Nearby Search para localizar los comercios
    en un radio de distancia clasificados bajo el tipo específico de Google.
    """
    if DEV_MODE or not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY.startswith("pega_tu"):
        logger.info(f"Modo Desarrollo: Retornando lista de competidores simulados para tipo: {google_type}.")
        # Generar competidores ficticios y realistas
        return [
            {
                "place_id": f"plc_mock_10{i}",
                "nombre": f"Competidor Simulado {i + 1} ({google_type.capitalize()})",
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

    try:
        logger.info(f"Buscando competidores cercanos '{google_type}' en radio {radio}m...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        competidores = []
        if data.get("status") in ["OK", "ZERO_RESULTS"]:
            for item in data.get("results", []):
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
            return competidores
        else:
            status_err = data.get("status", "UNKNOWN_ERROR")
            logger.error(f"Google Places Nearby Search falló. Status: {status_err}")
            raise Exception(f"Google Places Nearby Search falló con estatus: {status_err}")

    except Exception as e:
        logger.error(f"Error en llamada a Google Places Nearby Search: {e}")
        raise e


def obtener_mapa_estatico(lat: float, lng: float, radio: int, competidores: list) -> bytes:
    """
    Genera una llamada a la API de Google Static Maps para obtener una imagen PNG del mapa
    con marcadores de diferentes colores: Azul para la ubicación propuesta, Rojo para los competidores.
    Retorna los bytes de la imagen.
    """
    if DEV_MODE or not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY.startswith("pega_tu"):
        logger.info("Modo Desarrollo: Evitando llamada a Google Static Maps. Retornando None.")
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

    # El marcador del centro (ubicación propuesta) será azul y con etiqueta 'O'
    markers = [f"color:blue|label:O|{lat},{lng}"]

    # Agregar competidores (rojo)
    # Limitamos a 10 competidores para no exceder límites de URL de Static Maps
    comp_added = 0
    for comp in competidores:
        if comp_added >= 10:
            break
        c_lat = comp.get("latitud")
        c_lng = comp.get("longitud")
        if c_lat and c_lng:
            markers.append(f"color:red|{c_lat},{c_lng}")
            comp_added += 1

    # Construir parámetros
    params = {
        "center": f"{lat},{lng}",
        "zoom": str(zoom),
        "size": "450x300",
        "maptype": "roadmap",
        "key": GOOGLE_MAPS_API_KEY,
    }

    # Agregar todos los marcadores al url
    marker_query = "&".join([f"markers={m}" for m in markers])
    full_url = f"{url}?center={params['center']}&zoom={params['zoom']}&size={params['size']}&maptype={params['maptype']}&key={params['key']}&{marker_query}"

    try:
        logger.info(f"Consultando Google Static Maps para coordenadas ({lat}, {lng})...")
        response = requests.get(full_url, timeout=15)
        response.raise_for_status()
        logger.info("Mapa estático recuperado con éxito desde Google Maps.")
        return response.content
    except Exception as e:
        logger.error(f"Error al obtener mapa estático de Google: {e}")
        return None
