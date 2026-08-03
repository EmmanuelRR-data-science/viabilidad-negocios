"""Servicio para cuestionario guiado de aliados (delegado a dominio)."""

from __future__ import annotations

from app.domain.aliados_guiados import (
    resolver_aliados_guiados,
    validar_config_guiada,
)
from app.schemas.domain.aliados_guiados import ResolucionAliadosGuiados


def procesar_configuracion_guiada(
    config: dict | None,
    rubro: str,
    *,
    modo: str = "automatico",
) -> ResolucionAliadosGuiados:
    """Valida y resuelve los atractores seleccionados por el usuario."""
    valid_config = validar_config_guiada(config, modo=modo)
    return resolver_aliados_guiados(valid_config, rubro)
