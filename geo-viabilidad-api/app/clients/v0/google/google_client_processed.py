from __future__ import annotations

import logging

from app.clients.v0.google.google_client_raw import (
    _google_api_disponible,
    buscar_coordenadas_por_direccion_raw,
    buscar_lugares_raw,
    buscar_por_proximidad_raw,
    obtener_direccion_raw,
    obtener_mapa_estatico_raw,
)
from app.core.config import settings
from app.schemas.v0.google.google_domain_schemas import (
    DireccionFisicaDomain,
    LugarDomain,
)

logger = logging.getLogger("google_client_processed")


def _truncar_texto(texto: str, *, max_len: int = 220) -> str:
    limpio = " ".join(str(texto or "").split())
    if len(limpio) <= max_len:
        return limpio
    return limpio[: max_len - 1].rstrip() + "…"


def obtener_detalle_lugar(place_id: str, *, max_reseñas: int = 3) -> dict:
    """Obtiene el estado operativo y reseñas más recientes de un lugar."""
    vacio = {"business_status": "UNKNOWN", "reseñas_google": []}
    if not place_id:
        return vacio

    if not _google_api_disponible():
        return vacio

    # Como detalle del lugar involucra llamadas a API details,
    # usamos requests directo en processed (o raw delegada)
    import requests

    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "business_status,reviews",
        "reviews_sort": "newest",
        "language": "es",
        "key": settings.GOOGLE_MAPS_API_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "OK":
            return vacio

        result = data.get("result", {})
        reseñas = []
        for item in result.get("reviews", [])[:max_reseñas]:
            texto = _truncar_texto(item.get("text", ""))
            ts = item.get("time")
            reseñas.append(
                {
                    "texto": texto,
                    "rating": int(item.get("rating") or 0),
                    "autor": str(item.get("author_name") or "Usuario de Google"),
                    "fecha_relativa": str(item.get("relative_time_description") or ""),
                    "time": int(ts) if ts else None,
                }
            )
        return {
            "business_status": str(result.get("business_status") or "UNKNOWN"),
            "reseñas_google": reseñas,
        }
    except Exception as err:
        logger.error("Error al obtener detalle de Google para %s: %s", place_id, err)
        return vacio


def obtener_reseñas_lugar(place_id: str, *, max_reseñas: int = 3) -> list[dict]:
    return obtener_detalle_lugar(place_id, max_reseñas=max_reseñas).get("reseñas_google", [])


def enriquecer_lugar_con_vigencia(lugar: dict, *, max_reseñas: int = 3) -> None:
    from app.domain.vigencia_comercio import evaluar_vigencia_comercio, vigencia_sin_verificar

    if lugar.get("vigencia"):
        return

    place_id = lugar.get("place_id")
    if not place_id:
        lugar["vigencia"] = vigencia_sin_verificar()
        return

    detalle = obtener_detalle_lugar(place_id, max_reseñas=max_reseñas)
    lugar["business_status"] = detalle.get("business_status")
    if detalle.get("reseñas_google"):
        lugar["reseñas_google"] = detalle["reseñas_google"]
    elif "reseñas_google" not in lugar:
        lugar["reseñas_google"] = []

    lugar["vigencia"] = evaluar_vigencia_comercio(
        business_status=detalle.get("business_status"),
        reseñas_google=lugar.get("reseñas_google"),
    )


def enriquecer_lugares_con_vigencia(
    lugares: list[dict],
    *,
    limite: int = 15,
    max_reseñas: int = 2,
) -> None:
    consultados = 0
    for lugar in lugares:
        if consultados >= limite:
            break
        if not lugar.get("place_id"):
            continue
        enriquecer_lugar_con_vigencia(lugar, max_reseñas=max_reseñas)
        consultados += 1


def enriquecer_competidores_con_reseñas(
    competidores: list[dict],
    *,
    min_resenas: int = 5,
    max_reseñas_por_competidor: int = 2,
) -> None:
    for comp in competidores:
        if comp.get("vigencia"):
            continue
        if int(comp.get("user_ratings_total") or 0) < min_resenas:
            comp["reseñas_google"] = comp.get("reseñas_google") or []
            enriquecer_lugar_con_vigencia(comp, max_reseñas=max_reseñas_por_competidor)
            continue
        enriquecer_lugar_con_vigencia(comp, max_reseñas=max_reseñas_por_competidor)


def obtener_direccion(lat: float, lng: float) -> dict:
    """Mapea geocodificación a formato DireccionFisicaDomain."""
    response_dto = obtener_direccion_raw(lat, lng)
    if response_dto.status != "OK":
        domain = DireccionFisicaDomain()
        res = domain.model_dump()
        res["municipio"] = None
        res["pais"] = None
        return res

    result = response_dto.results[0]
    components = result.address_components

    calle = ""
    numero = ""
    colonia = ""
    cp = ""
    localidad = ""
    municipio = ""
    estado = ""
    pais = ""

    for comp in components:
        types = comp.types
        long_name = comp.long_name

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

    if not colonia:
        for comp in components:
            if "neighborhood" in comp.types:
                colonia = comp.long_name
                break

    domain = DireccionFisicaDomain(
        calle=calle or "Calle no especificada",
        numero=numero or "S/N",
        colonia=colonia or "Colonia no detectada",
        codigo_postal=cp or "00000",
        localidad=localidad or municipio or estado,
        estado=estado or "Estado no especificado",
        formato_completo=result.formatted_address or "Dirección no estructurada",
    )
    res = domain.model_dump()
    res["municipio"] = municipio or "Municipio no especificado"
    res["pais"] = pais or "México"
    return res


def buscar_competidores(
    lat: float,
    lng: float,
    radio: float,
    google_type: str,
    keyword: str | None = None,
) -> list[dict]:
    """Mapea Nearby Search raw a list de LugarDomain dicts con filtros."""
    raw_list = buscar_lugares_raw(lat, lng, radio, google_type, keyword)
    if not raw_list:
        return []

    tipos_genericos = {"establishment", "store", "point_of_interest"}
    competidores = []
    descartados = 0

    for item in raw_list:
        item_types = item.types
        if not keyword and google_type not in tipos_genericos and item_types and google_type not in item_types:
            descartados += 1
            continue

        domain = LugarDomain(
            place_id=item.place_id,
            nombre=item.name,
            latitud=item.geometry.location.lat,
            longitud=item.geometry.location.lng,
            rating=item.rating or 0.0,
            user_ratings_total=item.user_ratings_total or 0,
            direccion=item.vicinity or "Dirección no disponible",
            google_types=item.types,
        )
        competidores.append(domain.model_dump())

    if descartados:
        logger.info(
            "Filtro de relevancia Places: %d resultado(s) descartado(s) por no declarar tipo '%s'.",
            descartados,
            google_type,
        )
    return competidores


def buscar_competidores_por_proximidad(lat: float, lng: float, google_type: str) -> list[dict]:
    raw_list = buscar_por_proximidad_raw(lat, lng, google_type)
    res = []
    for item in raw_list:
        domain = LugarDomain(
            place_id=item.place_id,
            nombre=item.name,
            latitud=item.geometry.location.lat,
            longitud=item.geometry.location.lng,
            rating=item.rating or 0.0,
            user_ratings_total=item.user_ratings_total or 0,
            direccion=item.vicinity or "Dirección no disponible",
            google_types=item.types,
        )
        res.append(domain.model_dump())
    return res


def buscar_coordenadas_por_direccion(direccion: str) -> list[dict]:
    response_dto = buscar_coordenadas_por_direccion_raw(direccion)
    if response_dto.status != "OK":
        return []

    resultados = []
    for result in response_dto.results:
        resultados.append(
            {
                "direccion": result.formatted_address,
                "latitud": result.geometry.location.lat,
                "longitud": result.geometry.location.lng,
            }
        )
    return resultados


def obtener_mapa_estatico(
    lat: float,
    lng: float,
    radio: int,
    competidores: list,
    aliados: list | None = None,
    *,
    incluir_aliados: bool = False,
) -> bytes | None:
    return obtener_mapa_estatico_raw(lat, lng, radio, competidores, aliados, incluir_aliados=incluir_aliados)
