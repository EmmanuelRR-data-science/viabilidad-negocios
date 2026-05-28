import streamlit as st
import os
import zipfile
import tempfile
import io
import pandas as pd
import fiona
import pyproj
from shapely.geometry import shape
from shapely.ops import transform
import sqlalchemy
from sqlalchemy import text
import gc
import shutil

# Configuración de la página
st.set_page_config(
    page_title="GeoViabilidad Hook - Ingesta Administrativa",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo estético premium (Dark Mode con toques HSL e iluminación sutil)
st.markdown("""
<style>
    /* Estilos globales */
    .stApp {
        background-color: #0d0f12;
        color: #e2e8f0;
    }
    h1, h2, h3 {
        color: #ffffff;
        font-family: 'Inter', sans-serif;
    }
    .stMarkdown p {
        color: #94a3b8;
    }
    
    /* Contenedores tipo Glassmorphism */
    .glass-card {
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 24px;
        backdrop-filter: blur(10px);
        margin-bottom: 20px;
    }
    .metric-card {
        background: rgba(15, 23, 42, 0.6);
        border-left: 4px solid #6366f1;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    
    /* Botones sutiles */
    .stButton>button {
        background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 8px 16px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# Título Principal
st.markdown("""
<div class='glass-card'>
    <h1 style='margin:0; font-weight: 800; background: linear-gradient(to right, #818cf8, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
        🗺️ GeoViabilidad Hook
    </h1>
    <p style='margin: 5px 0 0 0; font-size: 1.1rem; color: #a5b4fc;'>
        Consola de Ingesta Geoespacial y Demográfica de INEGI - Panel de Administración
    </p>
</div>
""", unsafe_allow_html=True)

# Configuración de Base de Datos en el Sidebar
st.sidebar.markdown("### ⚙️ Conexión de Base de Datos")

# Leer variables de entorno con fallbacks locales por defecto
default_user = os.environ.get("DB_USER", "admin")
default_password = os.environ.get("DB_PASSWORD", "admin_password_safe")
default_host = os.environ.get("DB_HOST", "127.0.0.1")
default_port = os.environ.get("DB_PORT", "5435")
default_name = os.environ.get("DB_NAME", "geoanalisis")

db_user = st.sidebar.text_input("Usuario", value=default_user)
db_password = st.sidebar.text_input("Contraseña", value=default_password, type="password")
db_host = st.sidebar.text_input("Host", value=default_host)
db_port = st.sidebar.text_input("Puerto", value=default_port)
db_name = st.sidebar.text_input("Base de Datos", value=default_name)

# Habilitar SSL requerido si nos conectamos a un host remoto (como AWS RDS)
if db_host not in ["127.0.0.1", "localhost"]:
    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode=require"
else:
    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"



# Intentar conexión
@st.cache_resource(show_spinner=False)
def get_db_engine(url):
    try:
        engine = sqlalchemy.create_engine(url, pool_recycle=3600)
        # Validar conexión rápida
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine, None
    except Exception as e:
        return None, str(e)

def init_db_schemas(engine):
    try:
        with engine.connect() as conn:
            # Habilitar PostGIS si no está
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            
            # Tabla agebs_demografia
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS agebs_demografia (
                    id SERIAL PRIMARY KEY,
                    cve_ageb VARCHAR(13) UNIQUE NOT NULL,
                    entidad VARCHAR(2) NOT NULL,
                    municipio VARCHAR(3) NOT NULL,
                    pobtot INTEGER DEFAULT -1,
                    pobmas INTEGER DEFAULT -1,
                    pobfem INTEGER DEFAULT -1,
                    vivtot INTEGER DEFAULT -1,
                    geom GEOMETRY(Geometry, 4326)
                );
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agebs_geom ON agebs_demografia USING GIST (geom);"))
            
            # Tabla categorias_cruce
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS categorias_cruce (
                    id SERIAL PRIMARY KEY,
                    codigo_scian VARCHAR(10) UNIQUE NOT NULL,
                    nombre_scian VARCHAR(200) NOT NULL,
                    google_place_type VARCHAR(50) NOT NULL,
                    categoria_negocio VARCHAR(50) NOT NULL,
                    peso_competencia NUMERIC(3, 2) DEFAULT 1.0
                );
            """))
            
            # Semilla inicial para categorias_cruce si está vacía
            cnt = conn.execute(text("SELECT count(*) FROM categorias_cruce")).scalar() or 0
            if cnt == 0:
                conn.execute(text("""
                    INSERT INTO categorias_cruce (codigo_scian, nombre_scian, google_place_type, categoria_negocio, peso_competencia)
                    VALUES 
                        ('722515', 'Cafeterías y fuentes de sodas', 'cafe', 'cafeteria', 1.0),
                        ('722511', 'Restaurantes con servicio de preparación de alimentos a la carta', 'restaurant', 'restaurante_carta', 1.0),
                        ('722513', 'Restaurantes que preparan alimentos de consumo inmediato (pizzas, hamburguesas)', 'fast_food', 'comida_rapida', 1.0),
                        ('464111', 'Farmacias con venta de medicamentos', 'pharmacy', 'farmacia', 0.8),
                        ('461110', 'Comercio al por menor en tiendas de abarrotes, ultramarinos y misceláneas', 'convenience_store', 'abarrotes', 0.5),
                        ('713940', 'Gimnasios y centros de acondicionamiento físico del sector privado', 'gym', 'gimnasio', 1.2),
                        ('611110', 'Escuelas de educación preescolar y primaria del sector privado', 'school', 'escuela', 0.5),
                        ('812110', 'Salones de belleza, peluquerías y clínicas de belleza', 'beauty_salon', 'estetica', 1.0),
                        ('812210', 'Tintorerías y lavanderías del sector privado', 'laundry', 'lavanderia', 1.0),
                        ('621111', 'Consultorios médicos del sector privado', 'doctor', 'consultorio_medico', 0.7);
                """))
            
            # Tabla ordenes_pagos
            conn.execute(text("""
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
                    s3_key_reporte VARCHAR(255),
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_aprobacion TIMESTAMP
                );
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pago_user ON ordenes_pagos (cognito_user_id);"))
            
            # Tabla ingesta_tareas
            conn.execute(text("""
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
            """))
            
            # Tabla cache_analisis_api
            conn.execute(text("""
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
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_cache_coords ON cache_analisis_api (latitud, longitud, radio_metros, rubro, servicio_tipo);"))
            
            conn.commit()
        return True, None
    except Exception as e:
        return False, str(e)

engine, conn_error = get_db_engine(db_url)

if conn_error:
    st.sidebar.error(f"❌ Error de Conexión: {conn_error}")
    st.sidebar.warning("Asegúrate de que el contenedor de Docker esté activo y el puerto 5435 esté libre.")
else:
    st.sidebar.success("✔️ Base de Datos Conectada")
    
    # Inicialización automática de tablas en segundo plano al conectar
    success, init_error = init_db_schemas(engine)
    if success:
        st.sidebar.success("✔️ Tablas del Sistema Inicializadas")
    else:
        st.sidebar.error(f"❌ Error al inicializar tablas: {init_error}")

# --- UI CENTRAL ---

if not engine:
    st.info("💡 Por favor, configura y conecta la base de datos PostgreSQL en el panel de la izquierda para continuar.")
else:
    # Obtener estadísticas reales
    def get_stats():
        stats = {"total_agebs": 0, "con_geom": 0, "con_censo": 0, "estados": []}
        try:
            with engine.connect() as conn:
                stats["total_agebs"] = conn.execute(text("SELECT count(*) FROM agebs_demografia")).scalar() or 0
                stats["con_geom"] = conn.execute(text("SELECT count(*) FROM agebs_demografia WHERE geom IS NOT NULL")).scalar() or 0
                stats["con_censo"] = conn.execute(text("SELECT count(*) FROM agebs_demografia WHERE pobtot != -1")).scalar() or 0
                
                # Desglose por estado
                res = conn.execute(text("""
                    SELECT entidad, 
                           count(*) as total,
                           count(geom) as con_geom,
                           count(CASE WHEN pobtot != -1 THEN 1 END) as con_censo
                    FROM agebs_demografia
                    GROUP BY entidad
                    ORDER BY entidad
                """))
                stats["estados"] = [dict(row._mapping) for row in res]
        except Exception:
            pass
        return stats

    db_stats = get_stats()

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.markdown(f"""
        <div class='metric-card'>
            <h4 style='margin:0; color:#a5b4fc;'>Total de AGEBs Registradas</h4>
            <h2 style='margin:5px 0 0 0; font-size:2.5rem; font-weight:800;'>{db_stats['total_agebs']:,}</h2>
        </div>
        """, unsafe_allow_html=True)
    with col_m2:
        st.markdown(f"""
        <div class='metric-card' style='border-left-color: #10b981;'>
            <h4 style='margin:0; color:#a7f3d0;'>AGEBs con Cartografía</h4>
            <h2 style='margin:5px 0 0 0; font-size:2.5rem; font-weight:800;'>{db_stats['con_geom']:,}</h2>
        </div>
        """, unsafe_allow_html=True)
    with col_m3:
        st.markdown(f"""
        <div class='metric-card' style='border-left-color: #f59e0b;'>
            <h4 style='margin:0; color:#fde68a;'>AGEBs con Datos de Censo</h4>
            <h2 style='margin:5px 0 0 0; font-size:2.5rem; font-weight:800;'>{db_stats['con_censo']:,}</h2>
        </div>
        """, unsafe_allow_html=True)

    # Pestañas de Ingesta
    tab_shp, tab_csv, tab_auto, tab_status = st.tabs([
        "🗺️ 1. Cargar Cartografía (Shapefiles .zip)", 
        "📊 2. Cargar Demografía (Censo CSV .zip)",
        "⚡ 3. Ingesta Nacional Automática (3 GB)",
        "📋 4. Estado de Coberturas Cargadas"
    ])

    # 1. CARGA DE CARTOGRAFÍA (SHAPEFILE)
    with tab_shp:
        st.markdown("""
        ### Carga Manual de Cartografía Estatal
        Sube un archivo `.zip` comprimido que contenga los archivos de la cartografía vectorial del INEGI para un estado específico.
        El archivo debe incluir directamente en su raíz o subcarpeta los archivos `.shp`, `.shx`, `.dbf` y `.prj` del shapefile de AGEBs urbanas (ej. `*a.shp`).
        """)
        
        uploaded_shp_file = st.file_uploader(
            "Selecciona el archivo ZIP de Cartografía (ej. 01_aguascalientes.zip o similar)", 
            type=["zip"],
            key="shp_uploader"
        )
        
        if uploaded_shp_file is not None:
            st.success(f"Archivo subido temporalmente: {uploaded_shp_file.name} ({uploaded_shp_file.size/1024/1024:.2f} MB)")
            
            if st.button("Iniciar Procesamiento e Ingesta de Geometrías", key="btn_shp_process"):
                # Crear barra de progreso y log de texto
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                log_area = st.empty()
                
                logs = []
                def log(msg):
                    logs.append(msg)
                    log_area.text_area("Consola de Logs", value="\n".join(logs), height=250)
                
                log(f"Iniciando procesamiento de {uploaded_shp_file.name}...")
                
                # Crear directorios temporales seguros
                temp_dir = tempfile.mkdtemp()
                try:
                    # Guardar el zip en disco temporal
                    zip_path = os.path.join(temp_dir, "uploaded_shp.zip")
                    with open(zip_path, "wb") as f_zip:
                        f_zip.write(uploaded_shp_file.read())
                    
                    log("Descomprimiendo archivo zip...")
                    extract_path = os.path.join(temp_dir, "extracted")
                    os.makedirs(extract_path, exist_ok=True)
                    
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_path)
                    
                    # Buscar archivos shapefile de AGEBs (*a.shp)
                    shp_files = []
                    for root, dirs, files in os.walk(extract_path):
                        for file in files:
                            # Filtramos los archivos que terminan en 'a.shp' (AGEBs en INEGI)
                            # También aceptamos archivos genéricos .shp si no siguen el estándar estricto
                            if file.endswith('a.shp') or (file.endswith('.shp') and not any(file.endswith(x) for x in ['sia.shp', 'sil.shp', 'sip.shp', 'mun.shp', 'ent.shp'])):
                                shp_files.append(os.path.join(root, file))
                    
                    if not shp_files:
                        log("❌ ERROR: No se encontró ningún Shapefile de AGEBs válido (*a.shp) en el archivo zip.")
                        st.error("No se detectó un shapefile de AGEBs válido.")
                    else:
                        target_shp = shp_files[0]
                        log(f"Shapefile detectado: {os.path.basename(target_shp)}")
                        
                        # Abrir Shapefile con Fiona
                        with fiona.open(target_shp, 'r') as src:
                            src_crs = src.crs
                            geom_type = src.schema['geometry']
                            fields = list(src.schema['properties'].keys())
                            
                            log(f"CRS Original: {src_crs}")
                            log(f"Tipo de Geometría: {geom_type}")
                            log(f"Atributos en Shapefile: {fields}")
                            
                            # Configurar reproyector a EPSG:4326
                            # Fiona crs puede ser un dict o un string
                            proj_in = pyproj.CRS.from_user_input(src_crs)
                            proj_out = pyproj.CRS.from_epsg(4326)
                            transformer = pyproj.Transformer.from_crs(proj_in, proj_out, always_xy=True)
                            
                            features = list(src)
                            total_features = len(features)
                            log(f"Total de AGEBs a procesar en cartografía: {total_features}")
                            
                            inserted_count = 0
                            
                            # Procesar por lotes de 1,000 para optimizar transacciones
                            batch_size = 100
                            batch_data = []
                            
                            for idx, feat in enumerate(features):
                                cvegeo = feat['properties'].get('CVEGEO')
                                cve_ent = feat['properties'].get('CVE_ENT') or cvegeo[:2] if cvegeo else None
                                cve_mun = feat['properties'].get('CVE_MUN') or cvegeo[2:5] if cvegeo else None
                                
                                if not cvegeo:
                                    continue
                                
                                # Reproyectar geometría
                                shp_geom = shape(feat['geometry'])
                                # Reproyectar las coordenadas de metros a grados decimales
                                reprojected_geom = transform(transformer.transform, shp_geom)
                                
                                # Convertir a WKT para insertar directamente en PostGIS
                                geom_wkt = reprojected_geom.wkt
                                
                                batch_data.append({
                                    "cve_ageb": cvegeo,
                                    "entidad": cve_ent,
                                    "municipio": cve_mun,
                                    "wkt": geom_wkt
                                })
                                
                                # Ejecutar batch
                                if len(batch_data) >= batch_size or idx == total_features - 1:
                                    try:
                                        with engine.connect() as conn:
                                            # Consulta Upsert espacial
                                            # Si ya existe, actualiza geometría y entidad
                                            # Si no, crea fila demográfica vacía (-1)
                                            stmt = text("""
                                                INSERT INTO agebs_demografia 
                                                    (cve_ageb, entidad, municipio, geom, pobtot, pobmas, pobfem, vivtot)
                                                VALUES 
                                                    (:cve_ageb, :entidad, :municipio, ST_GeomFromText(:wkt, 4326), -1, -1, -1, -1)
                                                ON CONFLICT (cve_ageb)
                                                DO UPDATE SET 
                                                    geom = EXCLUDED.geom,
                                                    entidad = EXCLUDED.entidad,
                                                    municipio = EXCLUDED.municipio;
                                            """)
                                            conn.execute(stmt, batch_data)
                                            conn.commit()
                                        
                                        inserted_count += len(batch_data)
                                        batch_data = []
                                        
                                        # Actualizar barra
                                        pct = inserted_count / total_features
                                        progress_bar.progress(pct)
                                        status_text.text(f"Progreso: {inserted_count}/{total_features} polígonos procesados...")
                                    except Exception as db_ex:
                                        log(f"⚠️ Error en lote: {db_ex}")
                                        batch_data = []
                                        
                            log(f"✔️ PROCESO FINALIZADO. Se insertaron/actualizaron {inserted_count} geometrías de AGEBs en PostGIS.")
                            st.success(f"Se cargaron {inserted_count} polígonos geoespaciales con éxito!")
                            
                except Exception as ex:
                    log(f"❌ ERROR CRÍTICO durante el procesamiento: {ex}")
                    st.error(f"Falló el procesamiento: {ex}")
                finally:
                    # Limpieza agresiva de archivos y memoria
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    gc.collect()

    # 2. CARGA DE DEMOGRAFÍA (CSV CENSO)
    with tab_csv:
        st.markdown("""
        ### Carga Manual de Variables Demográficas
        Sube un archivo `.zip` que contenga el archivo CSV del censo del INEGI correspondiente a la estructura de AGEBs del estado (ej. `RESAGEBURB_01CSV20.zip`).
        El sistema procesará en modo streaming la información, filtrará automáticamente para extraer los consolidados por AGEB urbana (evitando las manzanas individuales) e insertará las variables críticas (`pobtot`, `pobmas`, `pobfem`, `vivtot`).
        """)
        
        uploaded_csv_file = st.file_uploader(
            "Selecciona el archivo ZIP del Censo CSV (ej. resageburb_01csv20.zip o similar)", 
            type=["zip"],
            key="csv_uploader"
        )
        
        if uploaded_csv_file is not None:
            st.success(f"Archivo demográfico subido temporalmente: {uploaded_csv_file.name} ({uploaded_csv_file.size/1024/1024:.2f} MB)")
            
            if st.button("Iniciar Procesamiento e Ingesta de Datos del Censo", key="btn_csv_process"):
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                log_area = st.empty()
                
                logs = []
                def log(msg):
                    logs.append(msg)
                    log_area.text_area("Consola de Logs", value="\n".join(logs), height=250)
                
                log(f"Abriendo archivo zip demográfico {uploaded_csv_file.name}...")
                
                try:
                    # Leer archivo directamente en memoria usando ZipFile sin guardar en disco
                    zip_data = io.BytesIO(uploaded_csv_file.read())
                    with zipfile.ZipFile(zip_data, 'r') as z:
                        csv_files = [f for f in z.namelist() if f.endswith('.csv')]
                        
                        if not csv_files:
                            log("❌ ERROR: No se encontró ningún archivo CSV de censo dentro del ZIP.")
                            st.error("No se encontró archivo CSV.")
                        else:
                            csv_target = csv_files[0]
                            log(f"CSV de Censo detectado: {csv_target}")
                            
                            # Leer el CSV con Pandas de forma optimizada
                            with z.open(csv_target) as csv_f:
                                # Leemos por chunks para mantener el consumo de memoria mínimo (OOM-Safe)
                                log("Leyendo y filtrando datos del censo (AGEBs únicamente, MZA = 0)...")
                                
                                # Leemos primero las columnas para verificar estructura
                                df_header = pd.read_csv(csv_f, encoding='utf-8-sig', nrows=2)
                                columns = list(df_header.columns)
                                log(f"Columnas encontradas en el censo: {len(columns)}")
                                
                                # Regresar puntero
                                csv_f.seek(0)
                                
                                # Columnas obligatorias a leer
                                required_cols = ['ENTIDAD', 'MUN', 'LOC', 'AGEB', 'MZA', 'POBTOT', 'POBFEM', 'POBMAS', 'VIVTOT']
                                for r_col in required_cols:
                                    if r_col not in columns:
                                        log(f"⚠️ Alerta: Columna {r_col} no detectada directamente. Intentando búsqueda flexible...")
                                
                                # Volver a abrir el archivo para el iterador
                                chunk_iter = pd.read_csv(
                                    z.open(csv_target),
                                    encoding='utf-8-sig',
                                    chunksize=2000,
                                    keep_default_na=False
                                )
                                
                                mapped_records = []
                                total_processed_rows = 0
                                
                                for chunk_idx, chunk in enumerate(chunk_iter):
                                    total_processed_rows += len(chunk)
                                    status_text.text(f"Filas del archivo CSV leídas: {total_processed_rows:,}")
                                    
                                    # Convertir MZA a numérico para filtrado seguro
                                    chunk['MZA_num'] = pd.to_numeric(chunk['MZA'], errors='coerce').fillna(-1)
                                    
                                    # Filtrar: AGEB != '0000' y MZA es 0
                                    # Esto nos da exactamente las filas del resumen agregado por AGEB
                                    filtered = chunk[(chunk['AGEB'] != '0000') & (chunk['MZA_num'] == 0)]
                                    
                                    for idx, row in filtered.iterrows():
                                        try:
                                            ent = int(row['ENTIDAD'])
                                            mun = int(row['MUN'])
                                            loc = int(row['LOC'])
                                            ageb_code = str(row['AGEB']).strip()
                                            
                                            # Formatear clave única: Estado(2) + Mun(3) + Loc(4) + AGEB(4)
                                            cvegeo = f"{ent:02d}{mun:03d}{loc:04d}{ageb_code}"
                                            
                                            # Limpiar variables numéricas del censo
                                            pobtot = int(pd.to_numeric(row['POBTOT'], errors='coerce') or 0)
                                            pobmas = int(pd.to_numeric(row['POBMAS'], errors='coerce') or 0)
                                            pobfem = int(pd.to_numeric(row['POBFEM'], errors='coerce') or 0)
                                            vivtot = int(pd.to_numeric(row['VIVTOT'], errors='coerce') or 0)
                                            
                                            mapped_records.append({
                                                "cve_ageb": cvegeo,
                                                "entidad": f"{ent:02d}",
                                                "municipio": f"{mun:03d}",
                                                "pobtot": pobtot,
                                                "pobmas": pobmas,
                                                "pobfem": pobfem,
                                                "vivtot": vivtot
                                            })
                                        except Exception:
                                            pass
                                
                                total_mapped = len(mapped_records)
                                log(f"✔️ Filtrado completo. Total de AGEBs válidas con datos demográficos: {total_mapped:,}")
                                
                                # Realizar inserción masiva por lotes (SQL Upsert)
                                log("Escribiendo datos demográficos en PostGIS...")
                                batch_size = 100
                                inserted_count = 0
                                
                                for start_idx in range(0, total_mapped, batch_size):
                                    batch = mapped_records[start_idx:start_idx+batch_size]
                                    
                                    with engine.connect() as conn:
                                        stmt = text("""
                                            INSERT INTO agebs_demografia 
                                                (cve_ageb, entidad, municipio, pobtot, pobmas, pobfem, vivtot)
                                            VALUES 
                                                (:cve_ageb, :entidad, :municipio, :pobtot, :pobmas, :pobfem, :vivtot)
                                            ON CONFLICT (cve_ageb)
                                            DO UPDATE SET 
                                                pobtot = EXCLUDED.pobtot,
                                                pobmas = EXCLUDED.pobmas,
                                                pobfem = EXCLUDED.pobfem,
                                                vivtot = EXCLUDED.vivtot;
                                        """)
                                        conn.execute(stmt, batch)
                                        conn.commit()
                                    
                                    inserted_count += len(batch)
                                    progress_bar.progress(inserted_count / total_mapped)
                                    status_text.text(f"Escribiendo en BD: {inserted_count}/{total_mapped}...")
                                
                                log(f"✔️ PROCESO FINALIZADO. Se insertaron/actualizaron {inserted_count} variables sociodemográficas en la base de datos.")
                                st.success(f"Se cargaron los datos demográficos de {inserted_count} AGEBs con éxito!")
                                
                except Exception as ex:
                    log(f"❌ ERROR CRÍTICO durante el procesamiento demográfico: {ex}")
                    st.error(f"Falló la ingesta demográfica: {ex}")
                finally:
                    gc.collect()

    # 3. INGESTA NACIONAL AUTOMÁTICA (3 GB)
    with tab_auto:
        st.markdown("""
        ### Ingesta Masiva y Automatizada de la República Mexicana
        Esta opción lee y une de forma **100% automatizada y secuencial** los 32 estados de México utilizando los archivos fuente de cartografía y censo que ya se encuentran en la carpeta del servidor `fuentes/` (`889463807469_s.zip` y `resageburb_XXcsv20.zip`).
        
        **Ventajas de la Ingesta Directa del Servidor:**
        *   **Cero Buffers de Navegador**: No requiere subir archivos por red, evitando caídas por falta de memoria (OOM-Safe).
        *   **Procesamiento por Lotes**: Une e inserta cada estado secuencialmente liberando memoria de inmediato (`gc.collect()`).
        *   **Idempotente**: Si se detiene o se vuelve a ejecutar, omitirá o actualizará los registros sin duplicados.
        """)
        
        # Verificar archivos en fuentes
        # Buscar en variables de entorno o resolver relativo al script de forma dinámica
        fuentes_dir = os.environ.get("FUENTES_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fuentes"))
        shp_zip_path = os.path.join(fuentes_dir, "889463807469_s.zip")
        
        archivos_listos = True
        if not os.path.exists(shp_zip_path):
            st.error(f"❌ No se encontró el archivo de cartografía nacional en `{shp_zip_path}`.")
            archivos_listos = False
        else:
            st.success("✔️ Cartografía Nacional Detectada (`889463807469_s.zip` - 3.1 GB)")
            
        # Contar cuántos CSVs de censo hay
        census_count = 0
        for f_name in os.listdir(fuentes_dir):
            if f_name.startswith("resageburb_") and f_name.endswith("csv20.zip"):
                census_count += 1
                
        if census_count < 32:
            st.warning(f"⚠️ Se detectaron {census_count}/32 archivos de censo demográfico en `fuentes/`.")
        else:
            st.success("✔️ Los 32 archivos de censo estatal están listos en `fuentes/`.")
            
        if archivos_listos:
            if st.button("Iniciar Ingesta de los 32 Estados", key="btn_auto_all"):
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                log_area = st.empty()
                
                logs = []
                def log(msg):
                    logs.append(msg)
                    log_area.text_area("Consola de Ingesta Nacional", value="\n".join(logs), height=350)
                
                log("Iniciando Pipeline de Ingesta Nacional en el Servidor...")
                
                try:
                    with zipfile.ZipFile(shp_zip_path, 'r') as z_main:
                        sub_zips = z_main.namelist()
                    
                    log(f"Detectados {len(sub_zips)} archivos estatales dentro del ZIP principal.")
                    
                    total_estados = 32
                    for state_num in range(1, 33):
                        state_str = f"{state_num:02d}"
                        log(f"\nProcesando ESTADO {state_str}/32...")
                        
                        # Buscar sub-zip de cartografía
                        target_sub_zip = None
                        for sz in sub_zips:
                            if sz.startswith(state_str + "_"):
                                target_sub_zip = sz
                                break
                                
                        if not target_sub_zip:
                            log(f"⚠️ Saltando estado {state_str}: No se encontró cartografía.")
                            continue
                            
                        # Buscar censo
                        census_name = f"resageburb_{state_str}csv20.zip"
                        census_path = os.path.join(fuentes_dir, census_name)
                        
                        if not os.path.exists(census_path):
                            log(f"⚠️ Saltando estado {state_str}: No se encontró censo demográfico.")
                            continue
                            
                        log(f"  - Cartografía: {target_sub_zip}")
                        log(f"  - Censo: {census_name}")
                        
                        temp_dir = tempfile.mkdtemp()
                        try:
                            # 1. Extraer cartografía del estado
                            with zipfile.ZipFile(shp_zip_path, 'r') as z_main:
                                sub_data = z_main.read(target_sub_zip)
                            
                            sub_io = io.BytesIO(sub_data)
                            with zipfile.ZipFile(sub_io, 'r') as z_sub:
                                z_sub.extractall(temp_dir)
                                
                            shp_files = []
                            for root, dirs, files in os.walk(temp_dir):
                                for file in files:
                                    if file.endswith('a.shp') or (file.endswith('.shp') and not any(file.endswith(x) for x in ['sia.shp', 'sil.shp', 'sip.shp', 'mun.shp', 'ent.shp'])):
                                        shp_files.append(os.path.join(root, file))
                                        
                            if not shp_files:
                                log("  ❌ ERROR: No se encontró shapefile de AGEBs.")
                                continue
                                
                            target_shp = shp_files[0]
                            
                            # 2. Reproyectar geometrías
                            geoms_dict = {}
                            with fiona.open(target_shp, 'r') as src:
                                src_crs = src.crs
                                proj_in = pyproj.CRS.from_user_input(src_crs)
                                proj_out = pyproj.CRS.from_epsg(4326)
                                transformer = pyproj.Transformer.from_crs(proj_in, proj_out, always_xy=True)
                                
                                for record in src:
                                    cvegeo = record['properties']['CVEGEO']
                                    cve_ent = record['properties'].get('CVE_ENT') or cvegeo[:2] if cvegeo else None
                                    cve_mun = record['properties'].get('CVE_MUN') or cvegeo[2:5] if cvegeo else None
                                    
                                    if not cvegeo:
                                        continue
                                        
                                    shp_geom = shape(record['geometry'])
                                    reprojected = transform(transformer.transform, shp_geom)
                                    
                                    geoms_dict[cvegeo] = {
                                        "geom_wkt": reprojected.wkt,
                                        "entidad": cve_ent,
                                        "municipio": cve_mun
                                    }
                                    
                            log(f"  - Geometrías cargadas: {len(geoms_dict):,}")
                            
                            # 3. Leer censo demográfico CSV
                            census_dict = {}
                            with zipfile.ZipFile(census_path, 'r') as z_cen:
                                csv_files = [f for f in z_cen.namelist() if f.endswith('.csv')]
                                if csv_files:
                                    with z_cen.open(csv_files[0]) as csv_f:
                                        chunk_iter = pd.read_csv(
                                            csv_f, 
                                            encoding='utf-8-sig', 
                                            chunksize=2000, 
                                            keep_default_na=False
                                        )
                                        for chunk in chunk_iter:
                                            chunk['MZA_num'] = pd.to_numeric(chunk['MZA'], errors='coerce').fillna(-1)
                                            filtered = chunk[(chunk['AGEB'] != '0000') & (chunk['MZA_num'] == 0)]
                                            for idx, row in filtered.iterrows():
                                                try:
                                                    ent = int(row['ENTIDAD'])
                                                    mun = int(row['MUN'])
                                                    loc = int(row['LOC'])
                                                    ageb_code = str(row['AGEB']).strip()
                                                    cvegeo = f"{ent:02d}{mun:03d}{loc:04d}{ageb_code}"
                                                    census_dict[cvegeo] = {
                                                        "pobtot": int(pd.to_numeric(row['POBTOT'], errors='coerce') or 0),
                                                        "pobmas": int(pd.to_numeric(row['POBMAS'], errors='coerce') or 0),
                                                        "pobfem": int(pd.to_numeric(row['POBFEM'], errors='coerce') or 0),
                                                        "vivtot": int(pd.to_numeric(row['VIVTOT'], errors='coerce') or 0)
                                                    }
                                                except Exception:
                                                    pass
                                                    
                            log(f"  - Censo demográfico cargado: {len(census_dict):,}")
                            
                            # 4. Fusión e inserción SQL bulk upsert
                            merged = []
                            all_keys = set(geoms_dict.keys()).union(census_dict.keys())
                            for key in all_keys:
                                g_data = geoms_dict.get(key)
                                c_data = census_dict.get(key)
                                
                                ent = g_data["entidad"] if g_data else key[:2]
                                mun = g_data["municipio"] if g_data else key[2:5]
                                wkt = g_data["geom_wkt"] if g_data else None
                                
                                merged.append({
                                    "cve_ageb": key,
                                    "entidad": ent,
                                    "municipio": mun,
                                    "pobtot": c_data["pobtot"] if c_data else -1,
                                    "pobmas": c_data["pobmas"] if c_data else -1,
                                    "pobfem": c_data["pobfem"] if c_data else -1,
                                    "vivtot": c_data["vivtot"] if c_data else -1,
                                    "wkt": wkt
                                })
                                
                            batch_size = 200
                            for s_idx in range(0, len(merged), batch_size):
                                batch = merged[s_idx : s_idx + batch_size]
                                with engine.connect() as conn:
                                    stmt = text("""
                                        INSERT INTO agebs_demografia 
                                            (cve_ageb, entidad, municipio, geom, pobtot, pobmas, pobfem, vivtot)
                                        VALUES 
                                            (
                                                :cve_ageb, :entidad, :municipio, 
                                                CASE WHEN :wkt IS NOT NULL THEN ST_GeomFromText(:wkt, 4326) ELSE NULL END, 
                                                :pobtot, :pobmas, :pobfem, :vivtot
                                            )
                                        ON CONFLICT (cve_ageb)
                                        DO UPDATE SET 
                                            geom = CASE WHEN EXCLUDED.geom IS NOT NULL THEN EXCLUDED.geom ELSE agebs_demografia.geom END,
                                            pobtot = CASE WHEN EXCLUDED.pobtot != -1 THEN EXCLUDED.pobtot ELSE agebs_demografia.pobtot END,
                                            pobmas = CASE WHEN EXCLUDED.pobmas != -1 THEN EXCLUDED.pobmas ELSE agebs_demografia.pobmas END,
                                            pobfem = CASE WHEN EXCLUDED.pobfem != -1 THEN EXCLUDED.pobfem ELSE agebs_demografia.pobfem END,
                                            vivtot = CASE WHEN EXCLUDED.vivtot != -1 THEN EXCLUDED.vivtot ELSE agebs_demografia.vivtot END;
                                    """)
                                    conn.execute(stmt, batch)
                                    conn.commit()
                                    
                            log(f"  ✔️ Estado {state_str} completado. {len(merged):,} AGEBs insertadas.")
                            
                        except Exception as inner_ex:
                            log(f"  ❌ Error en estado {state_str}: {inner_ex}")
                        finally:
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            gc.collect()
                            
                        # Actualizar progreso general de los 32 estados
                        progress_bar.progress(state_num / total_estados)
                        status_text.text(f"Progreso General: {state_num}/32 Estados procesados...")
                        
                    log("\n✔️ PROCESO DE INGESTA NACIONAL COMPLETADO CON ÉXITO.")
                    st.success("¡La base de datos nacional PostGIS ha sido alimentada de forma automática con éxito!")
                    st.rerun() # Recargar las métricas de la pantalla
                    
                except Exception as ex:
                    log(f"❌ ERROR GENERAL: {ex}")
                    st.error(f"Error general en la ingesta: {ex}")
                finally:
                    gc.collect()

    # 4. ESTADO DE COBERTURAS
    with tab_status:
        st.markdown("### Cobertura Espacial y Demográfica del Territorio en Base de Datos")
        st.write("A continuación se muestra el listado de Estados (Entidades Federativas) que tienen información cargada en el visor geográfico:")
        
        if not db_stats['estados']:
            st.info("Aún no has cargado ninguna cobertura. ¡Usa las pestañas de arriba para cargar tu primer estado!")
        else:
            df_states = pd.DataFrame(db_stats['estados'])
            df_states.columns = ["Código Estado", "AGEBs Totales", "Con Geometría", "Con Demografía"]
            
            # Formatear la tabla
            st.dataframe(df_states, use_container_width=True)
            
            # Gráfico de cobertura
            st.markdown("### Avance de Carga por Estado")
            st.bar_chart(
                df_states.set_index("Código Estado")[["Con Geometría", "Con Demografía"]],
                use_container_width=True
            )
