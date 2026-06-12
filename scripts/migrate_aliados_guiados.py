"""Migración: columnas modo guiado de aliados en ordenes_pagos."""
from __future__ import annotations

import os
import sys

import sqlalchemy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://admin:admin_password_safe@127.0.0.1:5435/geoanalisis",
)


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
