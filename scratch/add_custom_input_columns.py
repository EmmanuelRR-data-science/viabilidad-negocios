import logging
import os
import sys

from sqlalchemy import text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")


def migrate():
    try:
        logger.info("Executing database migration: adding custom free-text columns to 'ordenes_pagos'...")
        with engine.begin() as conn:
            conn.execute(
                text("""
                ALTER TABLE ordenes_pagos 
                ADD COLUMN IF NOT EXISTS competidores_adicionales TEXT,
                ADD COLUMN IF NOT EXISTS aliados_adicionales TEXT;
            """)
            )
            logger.info("Migration successful: custom free-text columns added (or already exist).")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise e


if __name__ == "__main__":
    migrate()
