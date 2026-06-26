"""Métricas agregadas para el dashboard administrativo."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AppUsuario, OrdenPago


@dataclass
class AdminMetrics:
    total_usuarios: int
    total_compradores: int
    total_ordenes: int
    ordenes_aprobadas: int
    ordenes_pendientes: int
    ingresos_aprobados_mxn: float
    tasa_conversion_pct: float


def fetch_admin_metrics(db: Session) -> AdminMetrics:
    total_usuarios = int(db.query(func.count(AppUsuario.id)).scalar() or 0)
    total_ordenes = int(db.query(func.count(OrdenPago.id)).scalar() or 0)
    ordenes_aprobadas = int(
        db.query(func.count(OrdenPago.id)).filter(OrdenPago.estado_pago == "approved").scalar() or 0
    )
    ordenes_pendientes = int(
        db.query(func.count(OrdenPago.id)).filter(OrdenPago.estado_pago == "pending").scalar() or 0
    )
    total_compradores = int(
        db.query(func.count(func.distinct(OrdenPago.cognito_user_id)))
        .filter(OrdenPago.estado_pago == "approved")
        .scalar()
        or 0
    )
    ingresos_raw = (
        db.query(func.coalesce(func.sum(OrdenPago.monto), 0))
        .filter(OrdenPago.estado_pago == "approved")
        .scalar()
    )
    ingresos = float(ingresos_raw or 0)
    if isinstance(ingresos_raw, Decimal):
        ingresos = float(ingresos_raw)

    tasa = round((total_compradores / total_usuarios) * 100, 1) if total_usuarios else 0.0

    return AdminMetrics(
        total_usuarios=total_usuarios,
        total_compradores=total_compradores,
        total_ordenes=total_ordenes,
        ordenes_aprobadas=ordenes_aprobadas,
        ordenes_pendientes=ordenes_pendientes,
        ingresos_aprobados_mxn=ingresos,
        tasa_conversion_pct=tasa,
    )
