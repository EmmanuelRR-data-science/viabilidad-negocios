import logging
import os

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError

from app.config import DEV_MODE
from app.middleware import UserFriendlyExceptionMiddleware
from app.payments import router as payments_router
from app.routes_analytics import router as analytics_router

logger = logging.getLogger("main")

# Inicializar FastAPI
app = FastAPI(
    title="GeoViabilidad Hook - API Pública",
    description="Backend unificado de API pública, procesamiento asíncrono y motor de cobros por Tiers.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Servir reportes en local de forma estática en modo desarrollo para permitir descargas transparentes
if DEV_MODE:
    logger.info("Modo Desarrollo Activo: Creando y montando directorio estático de reportes en /static/reports")
    os.makedirs("scratch/reports", exist_ok=True)
    app.mount("/static/reports", StaticFiles(directory="scratch/reports"), name="static_reports")


# 1. Configurar CORS (Permite que el frontend en S3/CloudFront consuma la API de forma segura)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, se recomienda restringir a tus dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Registrar el Middleware de Excepciones Amigables (User-Centric)
app.add_middleware(UserFriendlyExceptionMiddleware)

# Enrutador base de API
api_router = APIRouter()


@api_router.get("/health", tags=["Salud"])
def health_check():
    """
    Ruta de estado básica para verificar que el servicio FastAPI está encendido.
    """
    return {"status": "online", "service": "GeoViabilidad Hook Backend", "timestamp": "2026-05-29T14:30:00"}


@api_router.get("/error-test", tags=["Salud"])
def disparar_error_prueba(tipo: str = "db"):
    """
    Ruta de pruebas para verificar que el UserFriendlyExceptionMiddleware funciona correctamente.
    Dispara intencionalmente un OperationalError o una excepción general.
    """
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


# 3. Registrar routers
app.include_router(api_router)
app.include_router(payments_router)
app.include_router(analytics_router)

# Servir el frontend de forma estática en la raíz
if os.path.exists("frontend"):
    logger.info("Montando frontend estático de alta fidelidad en el punto de entrada raíz /")
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


@app.on_event("startup")
def startup_event():
    logger.info("=========================================================")
    logger.info("🚀 GeoViabilidad Hook API Iniciada Correctamente 🚀")
    logger.info("Consola interactiva disponible en: http://localhost:8000/docs")
    logger.info("=========================================================")
