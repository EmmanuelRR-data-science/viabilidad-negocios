"""Consultas y exportación de leads (usuarios Google + actividad comercial)."""

from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from geo_viabilidad_data.models import AppUsuario, OrdenPago
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from admin.services.filters import LeadFilters, end_of_day, start_of_day


def _format_datetime(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _leads_query(db: Session, filters: LeadFilters | None = None):
    ordenes_pagadas_expr = func.sum(case((OrdenPago.estado_pago == "approved", 1), else_=0))

    query = (
        db.query(
            AppUsuario.nombre.label("nombre"),
            AppUsuario.email.label("email"),
            AppUsuario.primera_sesion.label("primera_sesion"),
            AppUsuario.ultima_sesion.label("ultima_sesion"),
            func.count(OrdenPago.id).label("total_ordenes"),
            ordenes_pagadas_expr.label("ordenes_pagadas"),
            func.max(OrdenPago.rubro).label("rubro_reciente"),
            func.max(OrdenPago.tier_adquirido).label("tier_reciente"),
            func.max(OrdenPago.fecha_creacion).label("ultima_orden"),
        )
        .outerjoin(OrdenPago, OrdenPago.cognito_user_id == AppUsuario.google_sub)
        .group_by(
            AppUsuario.id,
            AppUsuario.nombre,
            AppUsuario.email,
            AppUsuario.primera_sesion,
            AppUsuario.ultima_sesion,
        )
    )

    if filters:
        if filters.q:
            like = f"%{filters.q}%"
            query = query.filter((AppUsuario.nombre.ilike(like)) | (AppUsuario.email.ilike(like)))
        if filters.desde:
            query = query.filter(AppUsuario.ultima_sesion >= start_of_day(filters.desde))
        if filters.hasta:
            query = query.filter(AppUsuario.ultima_sesion <= end_of_day(filters.hasta))
        if filters.rubro:
            query = query.filter(OrdenPago.rubro.ilike(f"%{filters.rubro}%"))
        if filters.compro == "si":
            query = query.having(ordenes_pagadas_expr > 0)
        elif filters.compro == "no":
            query = query.having(ordenes_pagadas_expr == 0)

    return query.order_by(AppUsuario.ultima_sesion.desc())


def fetch_leads_rows(db: Session, filters: LeadFilters | None = None, limit: int = 250) -> list[dict]:
    """Agrega actividad de órdenes por usuario autenticado con Google."""
    rows = _leads_query(db, filters).limit(limit).all()

    payload: list[dict] = []
    for row in rows:
        ordenes_pagadas = int(row.ordenes_pagadas or 0)
        payload.append(
            {
                "nombre": row.nombre or "",
                "email": row.email,
                "primera_sesion": _format_datetime(row.primera_sesion),
                "ultima_sesion": _format_datetime(row.ultima_sesion),
                "total_ordenes": int(row.total_ordenes or 0),
                "compro_reporte": "Sí" if ordenes_pagadas > 0 else "No",
                "ordenes_pagadas": ordenes_pagadas,
                "rubro_reciente": row.rubro_reciente or "",
                "tier_reciente": row.tier_reciente or "",
                "ultima_orden": _format_datetime(row.ultima_orden),
            }
        )
    return payload


def build_leads_excel(db: Session, filters: LeadFilters | None = None) -> bytes:
    rows = fetch_leads_rows(db, filters=filters, limit=5000)
    df = pd.DataFrame(
        rows,
        columns=[
            "nombre",
            "email",
            "primera_sesion",
            "ultima_sesion",
            "total_ordenes",
            "compro_reporte",
            "ordenes_pagadas",
            "rubro_reciente",
            "tier_reciente",
            "ultima_orden",
        ],
    )
    df.rename(
        columns={
            "nombre": "Nombre",
            "email": "Correo",
            "primera_sesion": "Primera sesión",
            "ultima_sesion": "Última sesión",
            "total_ordenes": "Total órdenes",
            "compro_reporte": "¿Compró reporte?",
            "ordenes_pagadas": "Órdenes pagadas",
            "rubro_reciente": "Rubro reciente",
            "tier_reciente": "Tier reciente",
            "ultima_orden": "Fecha última orden",
        },
        inplace=True,
    )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Leads")
    buffer.seek(0)
    return buffer.getvalue()
