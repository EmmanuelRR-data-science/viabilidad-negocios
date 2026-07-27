"""Google clients v0 — processed API + giro filter + auth."""

from app.clients.v0.google.google_client_processed import (
    buscar_competidores,
    buscar_competidores_por_proximidad,
    buscar_coordenadas_por_direccion,
    enriquecer_competidores_con_reseñas,
    enriquecer_lugar_con_vigencia,
    enriquecer_lugares_con_vigencia,
    obtener_detalle_lugar,
    obtener_direccion,
    obtener_mapa_estatico,
    obtener_reseñas_lugar,
)
from app.clients.v0.google.google_giro_filter import (
    competidor_es_relevante_al_giro,
    filtrar_competidores_por_giro,
)

__all__ = [
    "buscar_competidores",
    "buscar_competidores_por_proximidad",
    "buscar_coordenadas_por_direccion",
    "competidor_es_relevante_al_giro",
    "enriquecer_competidores_con_reseñas",
    "enriquecer_lugar_con_vigencia",
    "enriquecer_lugares_con_vigencia",
    "filtrar_competidores_por_giro",
    "obtener_detalle_lugar",
    "obtener_direccion",
    "obtener_mapa_estatico",
    "obtener_reseñas_lugar",
]
