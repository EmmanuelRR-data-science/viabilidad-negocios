"""Inicialización de esquemas PostGIS y tablas del sistema (migrado desde Streamlit)."""

from __future__ import annotations

import json
from pathlib import Path

from geo_viabilidad_data.ingest_censo_helpers import ENSURE_SEGMENTO_COLUMNS_SQL
from sqlalchemy import text
from sqlalchemy.engine import Engine

from admin.exceptions import SchemaInitError


def init_db_schemas(engine: Engine) -> tuple[bool, str | None]:
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))

            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS agebs_demografia (
                    id SERIAL PRIMARY KEY,
                    cve_ageb VARCHAR(13) UNIQUE NOT NULL,
                    entidad VARCHAR(2) NOT NULL,
                    municipio VARCHAR(3) NOT NULL,
                    pobtot INTEGER DEFAULT -1,
                    pobmas INTEGER DEFAULT -1,
                    pobfem INTEGER DEFAULT -1,
                    vivtot INTEGER DEFAULT -1,
                    graproes NUMERIC(6,2) DEFAULT NULL,
                    vivpar_hab NUMERIC(8,2) DEFAULT NULL,
                    vph_autom NUMERIC(8,2) DEFAULT NULL,
                    vph_inter NUMERIC(8,2) DEFAULT NULL,
                    vph_pc NUMERIC(8,2) DEFAULT NULL,
                    geom GEOMETRY(Geometry, 4326)
                );
            """)
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agebs_geom ON agebs_demografia USING GIST (geom);"))
            conn.execute(
                text("""
                ALTER TABLE agebs_demografia
                  ADD COLUMN IF NOT EXISTS graproes NUMERIC(6,2) DEFAULT NULL,
                  ADD COLUMN IF NOT EXISTS vivpar_hab NUMERIC(8,2) DEFAULT NULL,
                  ADD COLUMN IF NOT EXISTS vph_autom NUMERIC(8,2) DEFAULT NULL,
                  ADD COLUMN IF NOT EXISTS vph_inter NUMERIC(8,2) DEFAULT NULL,
                  ADD COLUMN IF NOT EXISTS vph_pc NUMERIC(8,2) DEFAULT NULL;
            """)
            )
            conn.execute(text(ENSURE_SEGMENTO_COLUMNS_SQL))

            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS categorias_cruce (
                    id SERIAL PRIMARY KEY,
                    codigo_scian VARCHAR(10) UNIQUE NOT NULL,
                    nombre_scian VARCHAR(200) NOT NULL,
                    google_place_type VARCHAR(50) NOT NULL,
                    categoria_negocio VARCHAR(50) NOT NULL,
                    peso_competencia NUMERIC(3, 2) DEFAULT 1.0
                );
            """)
            )

            cnt = conn.execute(text("SELECT count(*) FROM categorias_cruce")).scalar() or 0
            if cnt == 0:
                # Resolver la ruta de categorias_cruce.json de forma segura
                current_dir = Path(__file__).resolve().parent
                resources_dir = current_dir.parent / "resources"
                json_path = resources_dir / "categorias_cruce.json"

                with open(json_path, encoding="utf-8") as f:
                    seed_data = json.load(f)

                insert_stmt = text("""
                    INSERT INTO categorias_cruce (
                        codigo_scian, nombre_scian, google_place_type,
                        categoria_negocio, peso_competencia
                    )
                    VALUES (
                        :codigo_scian, :nombre_scian, :google_place_type,
                        :categoria_negocio, :peso_competencia
                    )
                """)
                conn.execute(insert_stmt, seed_data)

            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS ordenes_pagos (
                    id SERIAL PRIMARY KEY,
                    cognito_user_id VARCHAR(100) NOT NULL,
                    checkout_id VARCHAR(100) UNIQUE NOT NULL,
                    monto NUMERIC(10, 2) NOT NULL,
                    estado_pago VARCHAR(20) NOT NULL,
                    tier_adquirido VARCHAR(20) NOT NULL,
                    latitud NUMERIC(9, 6) NOT NULL,
                    longitud NUMERIC(9, 6) NOT NULL,
                    radio_metros INTEGER NOT NULL,
                    rubro VARCHAR(50) NOT NULL,
                    intenciones TEXT,
                    email VARCHAR(255) NOT NULL DEFAULT 'demo_sva@geoviabilidad.com',
                    s3_key_reporte VARCHAR(255),
                    competidores_seleccionados TEXT,
                    aliados_seleccionados TEXT,
                    competidores_adicionales TEXT,
                    aliados_adicionales TEXT,
                    modo_analisis_aliados VARCHAR(20) NOT NULL DEFAULT 'automatico',
                    config_aliados_guiados TEXT,
                    resultado_json TEXT,
                    foda_json TEXT,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_aprobacion TIMESTAMP
                );
            """)
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pago_user ON ordenes_pagos (cognito_user_id);"))

            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS ingesta_tareas (
                    id VARCHAR(100) PRIMARY KEY,
                    archivo_nombre VARCHAR(255) NOT NULL,
                    estado VARCHAR(20) NOT NULL,
                    progreso_porcentaje INTEGER DEFAULT 0,
                    registros_insertados INTEGER DEFAULT 0,
                    error_mensaje TEXT,
                    fecha_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_fin TIMESTAMP
                );
            """)
            )

            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS cache_analisis_api (
                    id SERIAL PRIMARY KEY,
                    latitud NUMERIC(9, 6) NOT NULL,
                    longitud NUMERIC(9, 6) NOT NULL,
                    radio_metros INTEGER NOT NULL,
                    rubro VARCHAR(50) NOT NULL,
                    servicio_tipo VARCHAR(20) NOT NULL,
                    payload_respuesta JSONB NOT NULL,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_cache_coords ON cache_analisis_api "
                    "(latitud, longitud, radio_metros, rubro, servicio_tipo);"
                )
            )

            conn.commit()
        return True, None
    except Exception as err:
        import logging

        logging.getLogger("admin.schema_init").exception("Error inicializando esquema: %s", err)

        friendly_error = SchemaInitError()
        return False, f"{friendly_error.message} {friendly_error.suggested_action or ''}".strip()
