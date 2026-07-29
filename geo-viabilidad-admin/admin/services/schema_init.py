"""Inicialización de esquemas PostGIS y tablas del sistema (migrado desde Streamlit)."""

from __future__ import annotations

from geo_viabilidad_data.ingest_censo_helpers import ENSURE_SEGMENTO_COLUMNS_SQL
from sqlalchemy import text
from sqlalchemy.engine import Engine


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
                conn.execute(
                    text("""
                    INSERT INTO categorias_cruce (
                        codigo_scian, nombre_scian, google_place_type,
                        categoria_negocio, peso_competencia
                    )
                    VALUES
                        ('722515', 'Cafeterías y fuentes de sodas', 'cafe', 'cafeteria', 1.0),
                        (
                            '722511',
                            'Restaurantes con servicio de preparación de alimentos a la carta',
                            'restaurant', 'restaurante_carta', 1.0
                        ),
                        (
                            '722513',
                            'Restaurantes que preparan alimentos de consumo inmediato '
                            '(pizzas, hamburguesas)',
                            'fast_food', 'comida_rapida', 1.0
                        ),
                        ('464111', 'Farmacias con venta de medicamentos', 'pharmacy', 'farmacia', 0.8),
                        (
                            '461110',
                            'Comercio al por menor en tiendas de abarrotes, '
                            'ultramarinos y misceláneas',
                            'convenience_store', 'abarrotes', 0.5
                        ),
                        (
                            '713940',
                            'Gimnasios y centros de acondicionamiento físico del sector privado',
                            'gym', 'gimnasio', 1.2
                        ),
                        (
                            '611110',
                            'Escuelas de educación preescolar y primaria del sector privado',
                            'school', 'escuela', 0.5
                        ),
                        (
                            '812110',
                            'Salones de belleza, peluquerías y clínicas de belleza',
                            'beauty_salon', 'estetica', 1.0
                        ),
                        ('812210', 'Tintorerías y lavanderías del sector privado', 'laundry', 'lavanderia', 1.0),
                        ('621111', 'Consultorios médicos del sector privado', 'doctor', 'consultorio_medico', 0.7);
                """)
                )

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
        return False, (
            "No se pudo inicializar o verificar el esquema de la base de datos. "
            "Revisa permisos de la BD y vuelve a abrir la página de ingesta."
        )
