"""Parseo de filtros de consulta para el panel admin."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time


def parse_date(value: str | None) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min)


def end_of_day(value: date) -> datetime:
    return datetime.combine(value, time.max)


@dataclass(frozen=True)
class LeadFilters:
    q: str | None = None
    compro: str | None = None
    rubro: str | None = None
    desde: date | None = None
    hasta: date | None = None

    @classmethod
    def from_request(cls, args) -> LeadFilters:
        compro = (args.get("compro") or "").strip().lower()
        if compro not in {"si", "no"}:
            compro = None
        q = (args.get("q") or "").strip() or None
        rubro = (args.get("rubro") or "").strip() or None
        return cls(
            q=q,
            compro=compro,
            rubro=rubro,
            desde=parse_date(args.get("desde")),
            hasta=parse_date(args.get("hasta")),
        )

    def to_query_dict(self) -> dict[str, str]:
        payload: dict[str, str] = {}
        if self.q:
            payload["q"] = self.q
        if self.compro:
            payload["compro"] = self.compro
        if self.rubro:
            payload["rubro"] = self.rubro
        if self.desde:
            payload["desde"] = self.desde.isoformat()
        if self.hasta:
            payload["hasta"] = self.hasta.isoformat()
        return payload


@dataclass(frozen=True)
class OrderFilters:
    q: str | None = None
    estado: str | None = None
    tier: str | None = None
    rubro: str | None = None
    desde: date | None = None
    hasta: date | None = None

    @classmethod
    def from_request(cls, args) -> OrderFilters:
        estado = (args.get("estado") or "").strip().lower()
        if estado not in {"pending", "approved", "rejected"}:
            estado = None
        tier = (args.get("tier") or "").strip().lower()
        if tier not in {"basico", "pro", "premium"}:
            tier = None
        q = (args.get("q") or "").strip() or None
        rubro = (args.get("rubro") or "").strip() or None
        return cls(
            q=q,
            estado=estado,
            tier=tier,
            rubro=rubro,
            desde=parse_date(args.get("desde")),
            hasta=parse_date(args.get("hasta")),
        )

    def to_query_dict(self) -> dict[str, str]:
        payload: dict[str, str] = {}
        if self.q:
            payload["q"] = self.q
        if self.estado:
            payload["estado"] = self.estado
        if self.tier:
            payload["tier"] = self.tier
        if self.rubro:
            payload["rubro"] = self.rubro
        if self.desde:
            payload["desde"] = self.desde.isoformat()
        if self.hasta:
            payload["hasta"] = self.hasta.isoformat()
        return payload
