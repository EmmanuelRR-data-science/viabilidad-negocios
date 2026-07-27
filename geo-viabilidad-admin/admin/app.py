"""Factory de la aplicación Flask para el panel administrativo."""

from __future__ import annotations

from flask import Flask, flash, redirect, url_for

from admin.auth import is_admin_logged_in
from admin.config import AdminConfig
from admin.routes import admin_bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(AdminConfig)
    app.register_blueprint(admin_bp)

    @app.errorhandler(413)
    def request_entity_too_large(_err):
        flash("El archivo supera el límite permitido (600 MB).", "danger")
        return redirect(f"{url_for('admin.ingesta')}#shapefile")

    @app.route("/")
    def root():
        if is_admin_logged_in():
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("admin.login"))

    @app.route("/health")
    def health():
        return {"status": "ok", "service": "admin-flask"}

    return app


app = create_app()
