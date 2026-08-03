"""Consultas y exportación de órdenes de pago."""

from __future__ import annotations

import io
from datetime import datetime
from decimal import Decimal

import pandas as pd
from geo_viabilidad_data.models import AppUsuario, OrdenPago
from sqlalchemy.orm import Session

from admin.services.filters import OrderFilters, end_of_day, start_of_day


def _format_datetime(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _format_money(value) -> str:
    if value is None:
        return "0.00"
    if isinstance(value, Decimal):
        return f"{float(value):,.2f}"
    return f"{float(value):,.2f}"


def _base_orders_query(db: Session, filters: OrderFilters | None = None):
    query = (
        db.query(
            OrdenPago.id.label("orden_id"),
            OrdenPago.checkout_id.label("checkout_id"),
            AppUsuario.nombre.label("nombre_usuario"),
            OrdenPago.email.label("email"),
            OrdenPago.estado_pago.label("estado_pago"),
            OrdenPago.tier_adquirido.label("tier"),
            OrdenPago.rubro.label("rubro"),
            OrdenPago.monto.label("monto_mxn"),
            OrdenPago.radio_metros.label("radio_metros"),
            OrdenPago.latitud.label("latitud"),
            OrdenPago.longitud.label("longitud"),
            OrdenPago.fecha_creacion.label("fecha_creacion"),
            OrdenPago.fecha_aprobacion.label("fecha_aprobacion"),
            OrdenPago.s3_key_reporte.label("pdf_listo"),
        )
        .outerjoin(AppUsuario, AppUsuario.google_sub == OrdenPago.cognito_user_id)
        .order_by(OrdenPago.fecha_creacion.desc())
    )
    return _apply_order_filters(query, filters)


def _apply_order_filters(query, filters: OrderFilters | None):
    if not filters:
        return query

    if filters.q:
        like = f"%{filters.q}%"
        query = query.filter(
            (OrdenPago.email.ilike(like))
            | (OrdenPago.checkout_id.ilike(like))
            | (OrdenPago.rubro.ilike(like))
            | (AppUsuario.nombre.ilike(like))
        )
    if filters.estado:
        query = query.filter(OrdenPago.estado_pago == filters.estado)
    if filters.tier:
        query = query.filter(OrdenPago.tier_adquirido == filters.tier)
    if filters.rubro:
        query = query.filter(OrdenPago.rubro.ilike(f"%{filters.rubro}%"))
    if filters.desde:
        query = query.filter(OrdenPago.fecha_creacion >= start_of_day(filters.desde))
    if filters.hasta:
        query = query.filter(OrdenPago.fecha_creacion <= end_of_day(filters.hasta))
    return query


def fetch_orders_rows(db: Session, filters: OrderFilters | None = None, limit: int = 250) -> list[dict]:
    rows = _base_orders_query(db, filters).limit(limit).all()
    payload: list[dict] = []
    for row in rows:
        payload.append(
            {
                "orden_id": row.orden_id,
                "checkout_id": row.checkout_id,
                "nombre_usuario": row.nombre_usuario or "",
                "email": row.email,
                "estado_pago": row.estado_pago,
                "tier": row.tier,
                "rubro": row.rubro,
                "monto_mxn": _format_money(row.monto_mxn),
                "radio_metros": row.radio_metros,
                "latitud": float(row.latitud) if row.latitud is not None else None,
                "longitud": float(row.longitud) if row.longitud is not None else None,
                "fecha_creacion": _format_datetime(row.fecha_creacion),
                "fecha_aprobacion": _format_datetime(row.fecha_aprobacion),
                "pdf_listo": "Sí" if row.pdf_listo else "No",
            }
        )
    return payload


def fetch_distinct_rubros(db: Session) -> list[str]:
    rows = db.query(OrdenPago.rubro).distinct().order_by(OrdenPago.rubro.asc()).all()
    return [row[0] for row in rows if row[0]]


def build_orders_excel(db: Session, filters: OrderFilters | None = None) -> bytes:
    rows = fetch_orders_rows(db, filters=filters, limit=5000)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(
            columns=[
                "orden_id",
                "checkout_id",
                "nombre_usuario",
                "email",
                "estado_pago",
                "tier",
                "rubro",
                "monto_mxn",
                "fecha_creacion",
                "fecha_aprobacion",
                "pdf_listo",
            ]
        )

    df.rename(
        columns={
            "orden_id": "ID orden",
            "checkout_id": "Checkout ID",
            "nombre_usuario": "Nombre usuario",
            "email": "Correo",
            "estado_pago": "Estado pago",
            "tier": "Tier",
            "rubro": "Rubro",
            "monto_mxn": "Monto MXN",
            "radio_metros": "Radio (m)",
            "latitud": "Latitud",
            "longitud": "Longitud",
            "fecha_creacion": "Fecha creación",
            "fecha_aprobacion": "Fecha aprobación",
            "pdf_listo": "PDF listo",
        },
        inplace=True,
    )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Ordenes")
    buffer.seek(0)
    return buffer.getvalue()
