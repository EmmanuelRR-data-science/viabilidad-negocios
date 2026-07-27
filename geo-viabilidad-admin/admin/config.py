"""Configuración del panel administrativo Flask."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class AdminConfig:
    SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY", "cambiar-en-produccion-admin-flask")
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "PhiQus")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "viabilidad-negocios")
    FUENTES_DIR = os.environ.get("FUENTES_DIR", "").strip()
    MAX_CONTENT_LENGTH = int(os.environ.get("ADMIN_MAX_UPLOAD_MB", "600")) * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 8 * 60 * 60  # 8 horas
