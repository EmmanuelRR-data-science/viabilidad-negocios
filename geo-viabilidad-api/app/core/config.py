import logging
import os
import sys

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configurar logging básico
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("config")

if sys.platform == "win32" and "PGPASSFILE" not in os.environ:
    os.environ["PGPASSFILE"] = r"C:\Users\Public\pgpass.conf"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- CONTROL DE DESARROLLO / PRODUCCIÓN ---
    DEV_MODE: bool = Field(default=True)

    # Almacenamiento de PDFs: local (scratch/reports) vs Amazon S3. Independiente de DEV_MODE.
    REPORTS_LOCAL_STORAGE: bool = Field(default=True)
    LOCAL_REPORTS_DIR: str = Field(default="scratch/reports")

    # Pagos simulados (Mercado Pago mock). Solo activo si PAYMENTS_MOCK=true explícitamente.
    PAYMENTS_MOCK: bool = Field(default=False)

    # --- CONFIGURACIONES AWS (S3, Bedrock, SES) ---
    AWS_REGION: str = Field(default="us-east-1")
    S3_REPORTS_BUCKET: str = Field(default="viabilidad-hook-informes")
    BEDROCK_MODEL_ID: str = Field(default="meta.llama3-70b-instruct-v1:0")
    SES_SENDER_EMAIL: str = Field(default="alertas@geoviabilidad.com")

    # --- MERCADO PAGO ---
    MERCADOPAGO_ACCESS_TOKEN: str = Field(default="")
    MERCADOPAGO_PUBLIC_KEY: str = Field(default="")
    MERCADOPAGO_SANDBOX: bool = Field(default=True)
    MERCADOPAGO_TEST_BUYER_EMAIL: str = Field(default="")
    MERCADOPAGO_WEBHOOK_SECRET: str = Field(default="")

    # --- GOOGLE MAPS API (Places & Geocoding) ---
    GOOGLE_MAPS_API_KEY: str = Field(default="", validation_alias="GOOGLE_MAPS_API_KEY")
    GOOGLE_PLACES_API_KEY: str = Field(default="", validation_alias="GOOGLE_PLACES_API_KEY")

    # --- GOOGLE OAUTH (Sign-In con Google) ---
    GOOGLE_OAUTH_CLIENT_ID: str = Field(default="")
    PUBLIC_APP_URL: str = Field(default="")

    # --- SESIÓN DE APLICACIÓN ---
    SESSION_SECRET: str = Field(default="")
    SESSION_TTL_SECONDS: int = Field(default=3600)
    SESSION_COOKIE_NAME: str = Field(default="gv_session")
    DOWNLOAD_TOKEN_TTL_SECONDS: int = Field(default=600)

    # --- CORS ---
    CORS_ORIGINS_RAW: str = Field(default="", validation_alias="CORS_ORIGINS")

    # --- BESTTIME PEATONAL API ---
    BESTTIME_API_KEY: str = Field(default="", validation_alias="BESTTIME_API_KEY")
    BEST_TIME_API_KEY: str = Field(default="", validation_alias="BEST_TIME_API_KEY")
    BESTTIME_CLIENT_ID: str = Field(default="")

    # --- LLM PROVIDER SELECTION ---
    LLM_PROVIDER: str = Field(default="")
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile")
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")

    # Atributos derivados que no provienen directamente de env vars
    AWS_ENABLED: bool = False
    CORS_ORIGINS: list[str] = []
    OPENAPI_DOCS_URL: str | None = None
    OPENAPI_REDOC_URL: str | None = None
    OPENAPI_URL: str | None = None

    @model_validator(mode="after")
    def populate_derived_fields(self) -> "Settings":
        self.AWS_ENABLED = not self.DEV_MODE

        # Google Maps Key Fallback
        if not self.GOOGLE_MAPS_API_KEY and self.GOOGLE_PLACES_API_KEY:
            self.GOOGLE_MAPS_API_KEY = self.GOOGLE_PLACES_API_KEY

        # BestTime Key Fallback
        if not self.BESTTIME_API_KEY and self.BEST_TIME_API_KEY:
            self.BESTTIME_API_KEY = self.BEST_TIME_API_KEY

        self.PUBLIC_APP_URL = self.PUBLIC_APP_URL.rstrip("/")

        # Session Secret validation
        default_dev_session_secret = "dev-insecure-session-secret-change-me"
        if not self.SESSION_SECRET:
            self.SESSION_SECRET = default_dev_session_secret if self.DEV_MODE else ""

        if not self.SESSION_SECRET:
            raise ValueError("SESSION_SECRET es obligatorio cuando DEV_MODE=false.")
        if not self.DEV_MODE and (self.SESSION_SECRET == default_dev_session_secret or len(self.SESSION_SECRET) < 32):
            raise ValueError(
                "SESSION_SECRET de producción debe tener al menos 32 caracteres "
                "y no usar el valor por defecto de desarrollo."
            )

        # CORS Parsing
        origins = []
        if self.CORS_ORIGINS_RAW:
            origins.extend(o.strip().rstrip("/") for o in self.CORS_ORIGINS_RAW.split(",") if o.strip())
        if self.PUBLIC_APP_URL:
            origins.append(self.PUBLIC_APP_URL)
        if self.DEV_MODE:
            origins.extend(
                [
                    "http://localhost:8000",
                    "http://127.0.0.1:8000",
                    "http://localhost:8001",
                    "http://127.0.0.1:8001",
                ]
            )
        # Deduplicar
        seen = set()
        unique = []
        for o in origins:
            if o and o not in seen:
                seen.add(o)
                unique.append(o)
        self.CORS_ORIGINS = unique

        if not self.DEV_MODE and not self.CORS_ORIGINS:
            raise ValueError(
                "CORS_ORIGINS o PUBLIC_APP_URL deben definirse cuando DEV_MODE=false (allowlist obligatoria)."
            )

        # LLM Provider default
        if not self.LLM_PROVIDER:
            self.LLM_PROVIDER = "groq" if self.DEV_MODE else "bedrock"
        self.LLM_PROVIDER = self.LLM_PROVIDER.lower().strip()

        # OpenAPI URLs
        self.OPENAPI_DOCS_URL = "/docs" if self.DEV_MODE else None
        self.OPENAPI_REDOC_URL = "/redoc" if self.DEV_MODE else None
        self.OPENAPI_URL = "/api/openapi.json" if self.DEV_MODE else None

        return self


settings = Settings()

logger.info(
    "Configuración cargada en Modo: %s | Pagos: %s | Reportes PDF: %s",
    "PRUEBAS (Groq + datos reales; AWS omitido)" if settings.DEV_MODE else "PRODUCCIÓN (AWS Activo)",
    "MOCK (sin Mercado Pago real)" if settings.PAYMENTS_MOCK else "LIVE (Mercado Pago)",
    f"LOCAL ({settings.LOCAL_REPORTS_DIR})" if settings.REPORTS_LOCAL_STORAGE else f"S3 ({settings.S3_REPORTS_BUCKET})",
)
if settings.PAYMENTS_MOCK:
    logger.info(
        "Pagos MOCK activos: checkout simulado en la app. "
        "Para Mercado Pago: PAYMENTS_MOCK=false, credenciales MP y reiniciar API."
    )
elif settings.MERCADOPAGO_SANDBOX:
    logger.info("Mercado Pago en modo SANDBOX (Checkout Pro de prueba, pago como invitado).")
