import logging
import uuid

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Request
from fastapi.responses import JSONResponse
from requests.exceptions import RequestException
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("middleware")


class UserFriendlyExceptionMiddleware(BaseHTTPMiddleware):
    """
    Middleware global de captura y traducción de excepciones (User-Centric).
    Intercepta errores técnicos y los convierte en mensajes amigables y accionables
    para la interfaz de usuario, ocultando tracebacks y detalles sensibles en producción.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except OperationalError as exc:
            # Error específico de conexión a base de datos (PostgreSQL/RDS)
            transaction_id = f"err_db_{uuid.uuid4().hex[:8]}"
            logger.exception(f"[{transaction_id}] CRITICAL: Database Connection failed: {exc}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "friendly_message": "Estamos realizando un mantenimiento rápido en nuestra base de datos.",
                    "suggested_action": "Por favor, espera unos segundos e intenta recargar la página.",
                    "transaction_id": transaction_id,
                },
            )
        except SQLAlchemyError as exc:
            # Cualquier otro error SQL (queries mal construidas, violaciones de llaves, etc.)
            transaction_id = f"err_sql_{uuid.uuid4().hex[:8]}"
            logger.exception(f"[{transaction_id}] ERROR: Database query error: {exc}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "friendly_message": "No pudimos procesar la consulta en la base de datos temporalmente.",
                    "suggested_action": "Por favor, verifica los parámetros seleccionados e intenta de nuevo.",
                    "transaction_id": transaction_id,
                },
            )
        except (BotoCoreError, ClientError) as exc:
            # Fallos relacionados con AWS S3, Bedrock o SES
            transaction_id = f"err_aws_{uuid.uuid4().hex[:8]}"
            logger.exception(f"[{transaction_id}] CRITICAL: AWS SDK Error: {exc}")

            # Mensajes personalizados según el tipo de servicio fallido si es detectable
            friendly = "Estamos experimentando una alta demanda en nuestro motor de análisis estratégico inteligente."
            action = "Tu reporte cuantitativo está a salvo. Puedes intentar regenerar el análisis estratégico en unos minutos sin costo adicional."

            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "friendly_message": friendly,
                    "suggested_action": action,
                    "transaction_id": transaction_id,
                },
            )
        except RequestException as exc:
            # Errores en llamadas HTTP externas (como Google Places o BestTime)
            transaction_id = f"err_net_{uuid.uuid4().hex[:8]}"
            logger.exception(f"[{transaction_id}] ERROR: External HTTP request failed: {exc}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "friendly_message": "No pudimos conectar con los servidores de mapas satelitales.",
                    "suggested_action": "El resto de la demografía del INEGI está lista. Intenta consultar el mapa de nuevo en unos minutos.",
                    "transaction_id": transaction_id,
                },
            )
        except Exception as exc:
            # Errores generales inesperados del sistema
            transaction_id = f"err_sys_{uuid.uuid4().hex[:8]}"
            logger.exception(f"[{transaction_id}] UNEXPECTED ERROR: {exc}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "friendly_message": "Ha surgido un inconveniente inesperado en la plataforma.",
                    "suggested_action": "No te preocupes; nuestro equipo técnico ha sido notificado automáticamente. Por favor, intenta tu consulta en breve.",
                    "transaction_id": transaction_id,
                },
            )
