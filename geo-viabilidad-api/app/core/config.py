import logging
import os
import sys
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PaymentsMode = Literal["mock", "sandbox", "live"]
_PAYMENTS_MODES: frozenset[str] = frozenset({"mock", "sandbox", "live"})

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

    # Modo de pagos canónico: mock | sandbox | live (configuración de despliegue, no lógica DEV).
    PAYMENTS_MODE: str = Field(default="")
    # Legacy (retrocompat): si PAYMENTS_MODE está vacío, se deriva de estos flags.
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

    # Atributos derivados (no se cargan desde env; se calculan en populate_derived_fields)
    AWS_ENABLED: bool = Field(default=False, exclude=True)
    OPENAPI_DOCS_URL: str | None = Field(default=None, exclude=True)
    OPENAPI_REDOC_URL: str | None = Field(default=None, exclude=True)
    OPENAPI_URL: str | None = Field(default=None, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def CORS_ORIGINS(self) -> list[str]:
        """Allowlist CORS derivada de env, PUBLIC_APP_URL y localhost en DEV."""
        origins: list[str] = []
        if self.CORS_ORIGINS_RAW:
            origins.extend(o.strip().rstrip("/") for o in self.CORS_ORIGINS_RAW.split(",") if o.strip())
        if self.PUBLIC_APP_URL:
            origins.append(self.PUBLIC_APP_URL.rstrip("/"))
        if self.DEV_MODE:
            origins.extend(
                [
                    "http://localhost:8000",
                    "http://127.0.0.1:8000",
                    "http://localhost:8001",
                    "http://127.0.0.1:8001",
                ]
            )
        seen: set[str] = set()
        unique: list[str] = []
        for origin in origins:
            if origin and origin not in seen:
                seen.add(origin)
                unique.append(origin)
        return unique

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

        # CORS Parsing (validación; lista en computed_field CORS_ORIGINS)
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

        self._resolve_payments_mode()

        return self

    def _resolve_payments_mode(self) -> None:
        """Unifica PAYMENTS_MODE con flags legacy y valida credenciales al arranque."""
        explicit = (self.PAYMENTS_MODE or "").lower().strip()
        if explicit:
            if explicit not in _PAYMENTS_MODES:
                raise ValueError(f"PAYMENTS_MODE debe ser mock, sandbox o live (recibido: {self.PAYMENTS_MODE!r}).")
            mode: PaymentsMode = explicit  # type: ignore[assignment]
        elif self.PAYMENTS_MOCK:
            mode = "mock"
        elif self.MERCADOPAGO_SANDBOX:
            mode = "sandbox"
        else:
            mode = "live"

        self.PAYMENTS_MODE = mode
        self.PAYMENTS_MOCK = mode == "mock"
        self.MERCADOPAGO_SANDBOX = mode == "sandbox"

        if mode == "mock":
            return

        missing: list[str] = []
        if not (self.MERCADOPAGO_ACCESS_TOKEN or "").strip():
            missing.append("MERCADOPAGO_ACCESS_TOKEN")
        if not (self.MERCADOPAGO_PUBLIC_KEY or "").strip():
            missing.append("MERCADOPAGO_PUBLIC_KEY")
        if not (self.MERCADOPAGO_WEBHOOK_SECRET or "").strip():
            missing.append("MERCADOPAGO_WEBHOOK_SECRET")
        if missing:
            raise ValueError(f"Con PAYMENTS_MODE={mode} son obligatorios: {', '.join(missing)}.")

        if not _https_public_app_url_valid(self.PUBLIC_APP_URL):
            raise ValueError(
                f"Con PAYMENTS_MODE={mode}, PUBLIC_APP_URL debe ser HTTPS público "
                "(no localhost ni IP privada). Ej.: https://tu-dominio.ngrok-free.dev"
            )

        token = self.MERCADOPAGO_ACCESS_TOKEN.strip()
        if mode == "live" and token.upper().startswith("TEST-"):
            raise ValueError("PAYMENTS_MODE=live no admite tokens TEST-; usa credenciales de producción (APP_USR-).")
        if mode == "sandbox" and not token.upper().startswith("TEST-"):
            logger.warning(
                "PAYMENTS_MODE=sandbox pero MERCADOPAGO_ACCESS_TOKEN no parece de prueba (TEST-). "
                "Verifica que no estés usando credenciales live por error."
            )


def _https_public_app_url_valid(url: str) -> bool:
    base = (url or "").strip().rstrip("/")
    if not base:
        return False
    try:
        parsed = urlparse(base)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        return False
    if host.startswith("192.168.") or host.startswith("10.") or host.startswith("172."):
        return False
    return True


settings = Settings()

_payments_log = {
    "mock": "MOCK (checkout simulado, sin Mercado Pago)",
    "sandbox": "SANDBOX (Checkout Pro de prueba)",
    "live": "LIVE (Checkout Pro producción)",
}
logger.info(
    "Configuración cargada en Modo: %s | Pagos: %s | Reportes PDF: %s",
    "PRUEBAS (Groq + datos reales; AWS omitido)" if settings.DEV_MODE else "PRODUCCIÓN (AWS Activo)",
    _payments_log.get(settings.PAYMENTS_MODE, settings.PAYMENTS_MODE),
    f"LOCAL ({settings.LOCAL_REPORTS_DIR})" if settings.REPORTS_LOCAL_STORAGE else f"S3 ({settings.S3_REPORTS_BUCKET})",
)
if settings.PAYMENTS_MODE == "mock":
    logger.info("Pagos MOCK: cambia PAYMENTS_MODE=sandbox|live + credenciales MP y reinicia web-api.")
