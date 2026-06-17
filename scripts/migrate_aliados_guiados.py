"""Migración: columnas modo guiado de aliados en ordenes_pagos."""
from __future__ import annotations

import os
import sys

import sqlalchemy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    user = os.environ.get("DB_USER", "admin")
    password = os.environ.get("DB_PASSWORD", "admin_password_safe")
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = os.environ.get("DB_PORT", "5435")
    name = os.environ.get("DB_NAME", "geoanalisis")
    DB_URL = f"postgresql://{user}:{password}@{host}:{port}/{name}"


def main() -> None:
    engine = sqlalchemy.create_engine(DB_URL)
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text(
                "ALTER TABLE ordenes_pagos "
                "ADD COLUMN IF NOT EXISTS modo_analisis_aliados VARCHAR(20) NOT NULL DEFAULT 'automatico'"
            )
        )
        conn.execute(
            sqlalchemy.text(
                "ALTER TABLE ordenes_pagos ADD COLUMN IF NOT EXISTS config_aliados_guiados TEXT"
            )
        )
    print("Migración aliados guiados aplicada.")


if __name__ == "__main__":
    main()
