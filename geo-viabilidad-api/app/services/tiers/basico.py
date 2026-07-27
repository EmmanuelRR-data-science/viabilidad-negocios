"""Estrategia de capacidades del tier Básico."""

from __future__ import annotations

from typing import Any

from app.services.tiers.registry import get_pdf_pages, get_tier_details


class BasicoTierStrategy:
    """Plan Básico: demografía + competencia mínima; sin Bedrock ni aliados guiados."""

    tier_id = "basico"

    def details(self) -> dict[str, Any]:
        return get_tier_details(self.tier_id)

    def uses_bedrock(self) -> bool:
        return False

    def uses_aliados_guiados(self) -> bool:
        return False

    def includes_static_map(self) -> bool:
        return False

    def includes_aliados_on_map(self) -> bool:
        return False

    def includes_multi_radio(self) -> bool:
        return False

    def pdf_pages(self) -> int:
        return get_pdf_pages(self.tier_id)

    def report_sections(self) -> list[str]:
        return [
            "portada",
            "resumen_ejecutivo",
            "demografia",
            "competencia",
            "conclusion",
        ]
