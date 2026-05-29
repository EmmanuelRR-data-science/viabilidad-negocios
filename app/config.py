import logging
import os

from dotenv import load_dotenv

# Configurar logging básico
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("config")

# Cargar archivo .env si existe
load_dotenv()

# --- CONTROL DE DESARROLLO / PRODUCCIÓN ---
DEV_MODE = os.environ.get("DEV_MODE", "True").lower() in ("true", "1", "t", "yes")

# --- CONEXIÓN A BASE DE DATOS (PostgreSQL + PostGIS) ---
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "admin_password_safe")
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "5435"))
DB_NAME = os.environ.get("DB_NAME", "geoanalisis")

# Habilitar SSL para AWS RDS si estamos en host remoto y fuera de localhost
if DB_HOST not in ["127.0.0.1", "localhost"]:
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
else:
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- CONFIGURACIONES AWS (S3, Bedrock, SES) ---
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_REPORTS_BUCKET = os.environ.get("S3_REPORTS_BUCKET", "viabilidad-hook-informes")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "meta.llama3-70b-instruct-v1:0")

# --- MERCADO PAGO ---
MERCADOPAGO_ACCESS_TOKEN = os.environ.get("MERCADOPAGO_ACCESS_TOKEN", "")

# --- GOOGLE MAPS API (Places & Geocoding) ---
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY") or os.environ.get("GOOGLE_PLACES_API_KEY", "")

# --- BESTTIME PEATONAL API ---
BESTTIME_API_KEY = os.environ.get("BESTTIME_API_KEY") or os.environ.get("BEST_TIME_API_KEY", "")
BESTTIME_CLIENT_ID = os.environ.get("BESTTIME_CLIENT_ID", "")

# --- AWS SES EMAIL SENDER ---
SES_SENDER_EMAIL = os.environ.get("SES_SENDER_EMAIL", "alertas@geoviabilidad.com")

logger.info(f"Configuración cargada en Modo: {'DESARROLLO (Mocks Activos)' if DEV_MODE else 'PRODUCCIÓN (AWS Activo)'}")
