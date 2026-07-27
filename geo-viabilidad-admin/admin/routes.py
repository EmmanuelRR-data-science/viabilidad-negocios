"""Rutas del panel administrativo Flask."""

from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for

from admin.auth import is_admin_logged_in, login_admin, login_required, logout_admin, verify_admin_credentials
from admin.clients.db import get_engine, session_scope
from admin.config import AdminConfig
from admin.exceptions import DatabaseUnavailableError
from admin.services.filters import LeadFilters, OrderFilters
from admin.services.ingest_dashboard import fetch_fuentes_status, fetch_ingest_dashboard_stats, resolve_fuentes_dir
from admin.services.ingest_flash_store import pop_ingest_payload, stash_ingest_payload
from admin.services.ingest_manual import (
    IngestResult,
    ingest_census_zip,
    ingest_nacional_all_states,
    ingest_shapefile_zip,
)
from admin.services.leads_export import build_leads_excel, fetch_leads_rows
from admin.services.metrics import fetch_admin_metrics
from admin.services.orders_query import build_orders_excel, fetch_distinct_rubros, fetch_orders_rows
from admin.services.schema_init import init_db_schemas

logger = logging.getLogger("admin.routes")

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _render(template: str, **context):
    context.setdefault("admin_user", session.get("admin_user"))
    return render_template(template, **context)


def _stash_ingest_result(result: IngestResult) -> None:
    token = stash_ingest_payload(
        {
            "success": result.success,
            "message": result.message,
            "inserted_count": result.inserted_count,
            "logs": result.logs[-80:],
        }
    )
    session["ingest_token"] = token


def _pop_ingest_flash():
    token = session.pop("ingest_token", None)
    return pop_ingest_payload(token)


def _redirect_ingesta(tab: str):
    return redirect(f"{url_for('admin.ingesta')}#{tab}")


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if is_admin_logged_in():
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if verify_admin_credentials(username, password):
            login_admin(username)
            flash("Sesión administrativa iniciada.", "success")
            next_url = request.args.get("next") or url_for("admin.dashboard")
            return redirect(next_url)
        flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("login.html")


@admin_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_admin()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@login_required
def dashboard():
    with session_scope() as db:
        metrics = fetch_admin_metrics(db)
        leads = fetch_leads_rows(db, limit=10)
        orders = fetch_orders_rows(db, limit=8)

    return _render(
        "dashboard.html",
        active_page="dashboard",
        metrics=metrics,
        leads=leads,
        orders=orders,
    )


@admin_bp.route("/usuarios")
@login_required
def usuarios():
    filters = LeadFilters.from_request(request.args)
    with session_scope() as db:
        leads = fetch_leads_rows(db, filters=filters)
        rubros = fetch_distinct_rubros(db)

    export_url = url_for("admin.export_usuarios_excel", **filters.to_query_dict())
    return _render(
        "usuarios.html",
        active_page="usuarios",
        leads=leads,
        filters=filters,
        rubros=rubros,
        total_resultados=len(leads),
        export_url=export_url,
    )


@admin_bp.route("/ordenes")
@login_required
def ordenes():
    filters = OrderFilters.from_request(request.args)
    with session_scope() as db:
        orders = fetch_orders_rows(db, filters=filters)
        rubros = fetch_distinct_rubros(db)

    export_url = url_for("admin.export_ordenes_excel", **filters.to_query_dict())
    return _render(
        "ordenes.html",
        active_page="ordenes",
        orders=orders,
        filters=filters,
        rubros=rubros,
        total_resultados=len(orders),
        export_url=export_url,
    )


@admin_bp.route("/usuarios/export.xlsx", methods=["GET"])
@login_required
def export_usuarios_excel():
    filters = LeadFilters.from_request(request.args)
    with session_scope() as db:
        excel_bytes = build_leads_excel(db, filters=filters)

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"geoviabilidad_leads_{stamp}.xlsx"
    return send_file(
        BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@admin_bp.route("/ordenes/export.xlsx", methods=["GET"])
@login_required
def export_ordenes_excel():
    filters = OrderFilters.from_request(request.args)
    with session_scope() as db:
        excel_bytes = build_orders_excel(db, filters=filters)

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"geoviabilidad_ordenes_{stamp}.xlsx"
    return send_file(
        BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@admin_bp.route("/ingesta")
@login_required
def ingesta():
    engine = get_engine()
    schema_ok, schema_error = init_db_schemas(engine)
    fuentes_dir = resolve_fuentes_dir(AdminConfig.FUENTES_DIR or None)
    fuentes = fetch_fuentes_status(fuentes_dir)

    try:
        stats = fetch_ingest_dashboard_stats(engine)
        db_connected = True
    except Exception as err:
        logger.exception("Fallo al leer estadísticas de ingesta: %s", err)
        stats = None
        db_connected = False
        friendly = DatabaseUnavailableError(technical=str(err))
        schema_error = schema_error or friendly.message

    return _render(
        "ingesta.html",
        active_page="ingesta",
        stats=stats,
        fuentes=fuentes,
        schema_ok=schema_ok,
        schema_error=schema_error,
        db_connected=db_connected,
        ingest_flash=_pop_ingest_flash(),
    )


@admin_bp.route("/ingesta/shapefile", methods=["POST"])
@login_required
def ingesta_shapefile():
    upload = request.files.get("shapefile_zip")
    if not upload or not upload.filename:
        flash("Selecciona un archivo ZIP de cartografía.", "warning")
        return _redirect_ingesta("shapefile")
    if not upload.filename.lower().endswith(".zip"):
        flash("El archivo de cartografía debe ser .zip", "danger")
        return _redirect_ingesta("shapefile")

    result = ingest_shapefile_zip(get_engine(), upload.read(), upload.filename)
    _stash_ingest_result(result)
    flash(result.message, "success" if result.success else "danger")
    return _redirect_ingesta("shapefile")


@admin_bp.route("/ingesta/censo", methods=["POST"])
@login_required
def ingesta_censo():
    upload = request.files.get("censo_zip")
    if not upload or not upload.filename:
        flash("Selecciona un archivo ZIP del censo CSV.", "warning")
        return _redirect_ingesta("censo")
    if not upload.filename.lower().endswith(".zip"):
        flash("El archivo demográfico debe ser .zip", "danger")
        return _redirect_ingesta("censo")

    result = ingest_census_zip(get_engine(), upload.read(), upload.filename)
    _stash_ingest_result(result)
    flash(result.message, "success" if result.success else "danger")
    return _redirect_ingesta("censo")


@admin_bp.route("/ingesta/nacional", methods=["POST"])
@login_required
def ingesta_nacional():
    fuentes_dir = resolve_fuentes_dir(AdminConfig.FUENTES_DIR or None)
    result = ingest_nacional_all_states(get_engine(), fuentes_dir)
    _stash_ingest_result(result)
    flash(result.message, "success" if result.success else "danger")
    return _redirect_ingesta("nacional")
