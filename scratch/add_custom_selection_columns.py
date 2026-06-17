import logging

from sqlalchemy import text

from app.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")


def migrate():
    try:
        logger.info("Executing database migration: adding custom selection columns to 'ordenes_pagos'...")
        with engine.begin() as conn:
            conn.execute(
                text("""
                ALTER TABLE ordenes_pagos 
                ADD COLUMN IF NOT EXISTS competidores_seleccionados TEXT,
                ADD COLUMN IF NOT EXISTS aliados_seleccionados TEXT;
            """)
            )
            logger.info("Migration successful: custom selection columns added (or already exist).")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise e


if __name__ == "__main__":
    migrate()
