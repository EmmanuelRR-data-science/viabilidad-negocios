import logging
import os
import sys

from dotenv import load_dotenv

# Configurar logging básico
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("config")

# psycopg2 en Windows falla si el home tiene caracteres no-ASCII (OneDrive/acentos).
# Solo forzar PGPASSFILE en ese caso; en Linux/macOS no tocar.
if sys.platform == "win32" and "PGPASSFILE" not in os.environ:
    os.environ["PGPASSFILE"] = r"C:\Users\Public\pgpass.conf"

load_dotenv()

# --- CONTROL DE DESARROLLO / PRODUCCIÓN ---
DEV_MODE = os.environ.get("DEV_MODE", "True").lower() in ("true", "1", "t", "yes")

# Almacenamiento de PDFs: local (scratch/reports) vs Amazon S3. Independiente de DEV_MODE.
REPORTS_LOCAL_STORAGE = os.environ.get("REPORTS_LOCAL_STORAGE", "true").lower() in (
    "true",
    "1",
    "t",
    "yes",
)
LOCAL_REPORTS_DIR = os.environ.get("LOCAL_REPORTS_DIR", "scratch/reports")

# Pagos simulados (Mercado Pago mock). Solo activo si PAYMENTS_MOCK=true explícitamente.
PAYMENTS_MOCK = os.environ.get("PAYMENTS_MOCK", "").lower() in ("true", "1", "t", "yes")

# --- CONEXIÓN A BASE DE DATOS (PostgreSQL + PostGIS) ---

# --- CONFIGURACIONES AWS (S3, Bedrock, SES) — solo producción ---
AWS_ENABLED = not DEV_MODE
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_REPORTS_BUCKET = os.environ.get("S3_REPORTS_BUCKET", "viabilidad-hook-informes")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "meta.llama3-70b-instruct-v1:0")

# --- MERCADO PAGO ---
MERCADOPAGO_ACCESS_TOKEN = os.environ.get("MERCADOPAGO_ACCESS_TOKEN", "").strip()
MERCADOPAGO_PUBLIC_KEY = os.environ.get("MERCADOPAGO_PUBLIC_KEY", "").strip()
MERCADOPAGO_SANDBOX = os.environ.get("MERCADOPAGO_SANDBOX", "true").lower() in (
    "true",
    "1",
    "t",
    "yes",
)
# Email del comprador de prueba (panel MP → Cuentas de prueba → Comprador). Evita mezclar cuentas reales.
MERCADOPAGO_TEST_BUYER_EMAIL = os.environ.get("MERCADOPAGO_TEST_BUYER_EMAIL", "").strip()

# --- GOOGLE MAPS API (Places & Geocoding) ---
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY") or os.environ.get("GOOGLE_PLACES_API_KEY", "")

# --- GOOGLE OAUTH (Sign-In con Google) ---
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
PUBLIC_APP_URL = os.environ.get("PUBLIC_APP_URL", "").strip().rstrip("/")

# --- SESIÓN DE APLICACIÓN (JWT propio; el ID token de Google no viaja en cada request) ---
_DEFAULT_DEV_SESSION_SECRET = "dev-insecure-session-secret-change-me"
SESSION_SECRET = os.environ.get("SESSION_SECRET", "").strip() or (_DEFAULT_DEV_SESSION_SECRET if DEV_MODE else "")
if not SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET es obligatorio cuando DEV_MODE=false.")
if not DEV_MODE and (SESSION_SECRET == _DEFAULT_DEV_SESSION_SECRET or len(SESSION_SECRET) < 32):
    raise RuntimeError(
        "SESSION_SECRET de producción debe tener al menos 32 caracteres y no usar el valor por defecto de desarrollo."
    )
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "3600"))
SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "gv_session").strip() or "gv_session"
DOWNLOAD_TOKEN_TTL_SECONDS = int(os.environ.get("DOWNLOAD_TOKEN_TTL_SECONDS", "600"))


# --- CORS (allowlist; nunca '*' con cookies) ---
def _parse_cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    origins: list[str] = []
    if raw:
        origins.extend(o.strip().rstrip("/") for o in raw.split(",") if o.strip())
    if PUBLIC_APP_URL:
        origins.append(PUBLIC_APP_URL)
    if DEV_MODE:
        origins.extend(
            [
                "http://localhost:8000",
                "http://127.0.0.1:8000",
                "http://localhost:8001",
                "http://127.0.0.1:8001",
            ]
        )
    # Deduplicar preservando orden
    seen: set[str] = set()
    unique: list[str] = []
    for o in origins:
        if o and o not in seen:
            seen.add(o)
            unique.append(o)
    return unique


CORS_ORIGINS = _parse_cors_origins()
if not DEV_MODE and not CORS_ORIGINS:
    raise RuntimeError("CORS_ORIGINS o PUBLIC_APP_URL deben definirse cuando DEV_MODE=false (allowlist obligatoria).")

# Secret de firma de webhooks Mercado Pago (panel → Webhooks → firma secreta)
MERCADOPAGO_WEBHOOK_SECRET = os.environ.get("MERCADOPAGO_WEBHOOK_SECRET", "").strip()

# --- BESTTIME PEATONAL API ---
BESTTIME_API_KEY = os.environ.get("BESTTIME_API_KEY") or os.environ.get("BEST_TIME_API_KEY", "")
BESTTIME_CLIENT_ID = os.environ.get("BESTTIME_CLIENT_ID", "")

# --- AWS SES EMAIL SENDER ---
SES_SENDER_EMAIL = os.environ.get("SES_SENDER_EMAIL", "alertas@geoviabilidad.com")

# --- LLM PROVIDER SELECTION ---
# Values: "groq" (default for DEV), "openai", "bedrock"
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq" if DEV_MODE else "bedrock").lower().strip()

# --- GROQ API FOR LOCAL LLM DEV TESTING ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# --- OPENAI API (alternative local provider) ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

logger.info(
    "Configuración cargada en Modo: %s | Pagos: %s | Reportes PDF: %s",
    "PRUEBAS (Groq + datos reales; AWS omitido)" if DEV_MODE else "PRODUCCIÓN (AWS Activo)",
    "MOCK (sin Mercado Pago real)" if PAYMENTS_MOCK else "LIVE (Mercado Pago)",
    f"LOCAL ({LOCAL_REPORTS_DIR})" if REPORTS_LOCAL_STORAGE else f"S3 ({S3_REPORTS_BUCKET})",
)
if PAYMENTS_MOCK:
    logger.info(
        "Pagos MOCK activos: checkout simulado en la app. "
        "Para Mercado Pago: PAYMENTS_MOCK=false, credenciales MP y reiniciar API."
    )
elif MERCADOPAGO_SANDBOX:
    logger.info("Mercado Pago en modo SANDBOX (Checkout Pro de prueba, pago como invitado).")
