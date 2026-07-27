import logging
import os
import uuid

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError

from app.core.config import DEV_MODE, LOCAL_REPORTS_DIR, PAYMENTS_MOCK, REPORTS_LOCAL_STORAGE
from app.core.middleware import LLMRateLimitMiddleware, UserFriendlyExceptionMiddleware
from app.exceptions import UserFacingError
from app.routers.auth import router as auth_router
from app.routers.v0.analytics import router as analytics_router
from app.routers.v0.payments import router as payments_router
from app.routers.v0.reports import router as reports_router

logger = logging.getLogger("main")

app = FastAPI(
    title="GeoViabilidad Hook - API Pública",
    description="Backend de API pública, procesamiento asíncrono y motor de cobros por Tiers.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/openapi.json",
)

if REPORTS_LOCAL_STORAGE:
    logger.info("Reportes PDF locales: montando %s en /static/reports", LOCAL_REPORTS_DIR)
    os.makedirs(LOCAL_REPORTS_DIR, exist_ok=True)
    app.mount("/static/reports", StaticFiles(directory=LOCAL_REPORTS_DIR), name="static_reports")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LLMRateLimitMiddleware)
app.add_middleware(UserFriendlyExceptionMiddleware)

api_router = APIRouter()


@api_router.get("/health", tags=["Salud"])
def health_check():
    return {
        "status": "online",
        "service": "GeoViabilidad Hook Backend",
        "timestamp": "2026-05-29T14:30:00",
        "dev_mode": DEV_MODE,
        "payments_mock": PAYMENTS_MOCK,
    }


@api_router.get("/error-test", tags=["Salud"])
def disparar_error_prueba(tipo: str = "db"):
    if tipo == "db":
        logger.info("[TEST] Disparando OperationalError simulado de base de datos...")
        raise OperationalError("SELECT 1", {}, Exception("Database Connection refused (Simulated)"))
    elif tipo == "aws":
        logger.info("[TEST] Disparando ClientError simulado de AWS Bedrock...")
        from botocore.exceptions import ClientError

        raise ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Simulated Bedrock Access Denied"}}, "InvokeModel"
        )
    else:
        logger.info("[TEST] Disparando excepción inesperada simulada...")
        raise Exception("Fallo lógico no controlado en memoria (Simulado)")


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
    from app.clients.v0.database import AppUsuario, Base, engine

    Base.metadata.create_all(bind=engine, tables=[AppUsuario.__table__])
    logger.info("=========================================================")
    logger.info("🚀 Geo Viabilidad API Iniciada Correctamente 🚀")
    logger.info("OpenAPI: http://localhost:8001/docs (directo) o http://localhost:8000/docs (vía nginx)")
    logger.info("=========================================================")
