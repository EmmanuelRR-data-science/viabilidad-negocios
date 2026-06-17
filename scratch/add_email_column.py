import logging

from sqlalchemy import text

from app.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")


def migrate():
    try:
        logger.info("Executing database migration: adding 'email' column to 'ordenes_pagos'...")
        with engine.begin() as conn:
            conn.execute(
                text("""
                ALTER TABLE ordenes_pagos 
                ADD COLUMN IF NOT EXISTS email VARCHAR(255) NOT NULL DEFAULT 'demo_sva@geoviabilidad.com';
            """)
            )
            logger.info("Migration successful: 'email' column added (or already exists).")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise e


if __name__ == "__main__":
    migrate()
