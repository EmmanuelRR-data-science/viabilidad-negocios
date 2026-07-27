"""Configuración de conexión a PostgreSQL (sin dependencias de FastAPI/Flask)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DB_USER = os.environ.get("DB_USER", "admin")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "admin_password_safe")
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "5435"))
DB_NAME = os.environ.get("DB_NAME", "geoanalisis")

DEV_MODE = os.environ.get("DEV_MODE", "True").lower() in ("true", "1", "t", "yes")

_LOCAL_DB_HOSTS = frozenset({"127.0.0.1", "localhost", "geo-analisis-db", "host.docker.internal"})


def build_database_url() -> str:
    if not DEV_MODE and DB_HOST not in _LOCAL_DB_HOSTS:
        return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
    return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


DATABASE_URL = build_database_url()
