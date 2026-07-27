"""DEPRECATED — use app.clients.v0.google instead.

This flat module is retained only for backward compatibility with external scripts.
Hot-path code MUST import from ``app.clients.v0.google``.
"""

from app.clients.v0.google import (  # noqa: F401
    buscar_competidores,
    buscar_competidores_por_proximidad,
    buscar_coordenadas_por_direccion,
    competidor_es_relevante_al_giro,
    enriquecer_competidores_con_reseñas,
    enriquecer_lugar_con_vigencia,
    enriquecer_lugares_con_vigencia,
    filtrar_competidores_por_giro,
    obtener_detalle_lugar,
    obtener_direccion,
    obtener_mapa_estatico,
    obtener_reseñas_lugar,
)
