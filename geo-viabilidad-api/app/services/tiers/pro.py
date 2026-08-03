"""Estrategia de capacidades del tier Pro."""

from __future__ import annotations

from typing import Any

from app.services.tiers.registry import get_pdf_pages, get_tier_details


class ProTierStrategy:
    """Plan Pro: más competencia + afluencia; sin aliados guiados Premium."""

    tier_id = "pro"

    def details(self) -> dict[str, Any]:
        return get_tier_details(self.tier_id)

    def uses_bedrock(self) -> bool:
        return True

    def uses_aliados_guiados(self) -> bool:
        return False

    def includes_static_map(self) -> bool:
        return True

    def includes_aliados_on_map(self) -> bool:
        return False

    def includes_multi_radio(self) -> bool:
        return True

    def pdf_pages(self) -> int:
        return get_pdf_pages(self.tier_id)

    def report_sections(self) -> list[str]:
        return [
            "portada",
            "resumen_ejecutivo",
            "demografia",
            "competencia",
            "afluencia",
            "foda",
            "conclusion",
        ]
