import logging
import os
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.middleware import AbuseRateLimitMiddleware, LLMRateLimitMiddleware, UserFriendlyExceptionMiddleware
from app.exceptions import UserFacingError
from app.routers.auth import router as auth_router
from app.routers.v0.analytics import router as analytics_router
from app.routers.v0.payments import router as payments_router
from app.routers.v0.reports import router as reports_router
from app.schemas.v0.health_schemas import HealthResponse

logger = logging.getLogger("main")

_OPENAPI_TAGS = [
    {
        "name": "Salud",
        "description": "Estado del servicio y utilidades de diagnóstico.",
    },
    {
        "name": "Autenticación",
        "description": "Configuración OAuth y login con Google (o tokens mock en desarrollo).",
    },
    {
        "name": "Motor Analítico e INEGI",
        "description": (
            "Análisis geoespacial: vista previa, geocodificación, resultado de orden y "
            "dump cuantitativo de debug (sin IA)."
        ),
    },
    {
        "name": "Transacciones y Pagos",
        "description": (
            "Preferencias de cobro, estado de órdenes, webhooks de Mercado Pago y "
            "webhook simulado cuando `settings.PAYMENTS_MOCK=true`."
        ),
    },
    {
        "name": "Reportes",
        "description": "Obtención y descarga del PDF ejecutivo asociado a una orden pagada.",
    },
]

app = FastAPI(
    title="GeoViabilidad Hook - API Pública",
    description=(
        "API del monorepo GeoViabilidad (v1.0.0).\n\n"
        "**Flujo típico de demo (Swagger):**\n"
        "1. `GET /health`\n"
        "2. Authorize con `Bearer mock-token` (solo `settings.DEV_MODE`) o sesión vía `/api/auth/google?for=swagger`\n"
        "3. `GET /api/analizar/debug/cuantitativo` (JSON sin IA, requiere `settings.DEV_MODE`)\n"
        "4. `POST /api/analizar/previa` → `POST /api/pagos/preferencia` → "
        "`POST /api/pagos/webhook-mock` → poll estado → descargar PDF\n\n"
        "Arquitectura: routers → services → clients/domain. "
        "Errores de negocio se exponen como mensajes user-centric."
    ),
    version="1.0.0",
    docs_url=settings.OPENAPI_DOCS_URL,
    redoc_url=settings.OPENAPI_REDOC_URL,
    openapi_url=settings.OPENAPI_URL,
    openapi_tags=_OPENAPI_TAGS,
)

# PDFs locales solo vía endpoint autenticado con token firmado (no StaticFiles público).
if settings.REPORTS_LOCAL_STORAGE:
    os.makedirs(settings.LOCAL_REPORTS_DIR, exist_ok=True)
    logger.info(
        "Reportes PDF locales en %s (sin mount /static/reports; descarga vía API firmada).",
        settings.LOCAL_REPORTS_DIR,
    )

_cors_origins = settings.CORS_ORIGINS or (["http://localhost:8000"] if settings.DEV_MODE else [])
logger.info("CORS allowlist: %s", _cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AbuseRateLimitMiddleware)
app.add_middleware(LLMRateLimitMiddleware)
app.add_middleware(UserFriendlyExceptionMiddleware)

api_router = APIRouter()


@api_router.get(
    "/health",
    tags=["Salud"],
    response_model=HealthResponse,
    summary="Health check",
    description="Confirma que la API responde. No expone flags de entorno ni configuración interna.",
)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="GeoViabilidad Hook Backend",
        timestamp=datetime.now(UTC).isoformat(),
    )


# Endpoints de diagnóstico removidos de producción.


@app.exception_handler(UserFacingError)
async def user_facing_error_handler(request: Request, exc: UserFacingError):
    transaction_id = f"err_usr_{uuid.uuid4().hex[:8]}"
    logger.warning("[%s] UserFacingError %s: %s", transaction_id, exc.code, exc.message)
    body: dict = {
        "status": "error",
        "friendly_message": exc.message,
        "transaction_id": transaction_id,
    }
    if exc.suggested_action:
        body["suggested_action"] = exc.suggested_action
    return JSONResponse(status_code=exc.status_code, content=body)


app.include_router(api_router)
app.include_router(auth_router)
app.include_router(payments_router)
app.include_router(analytics_router)
app.include_router(reports_router)


@app.on_event("startup")
def startup_event():
    from app.clients.v0.database import AppUsuario, Base, OrdenPago, engine

    Base.metadata.create_all(bind=engine, tables=[AppUsuario.__table__, OrdenPago.__table__])
    logger.info("=========================================================")
    logger.info("🚀 Geo Viabilidad API Iniciada Correctamente 🚀")
    if settings.DEV_MODE:
        logger.info("OpenAPI: http://localhost:8001/docs (directo) o http://localhost:8000/docs (vía nginx)")
    else:
        logger.info("OpenAPI/docs deshabilitados (settings.DEV_MODE=false).")
    logger.info("=========================================================")
