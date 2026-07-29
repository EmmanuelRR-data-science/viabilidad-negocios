import collections
import logging
import time
import uuid

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Request
from fastapi.responses import JSONResponse
from requests.exceptions import RequestException
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("middleware")

# ---------------------------------------------------------------------------
# Constantes de rate limiting
# ---------------------------------------------------------------------------
_RATE_LIMIT_WINDOW_SECS = 60  # Ventana deslizante en segundos
_RATE_LIMIT_MAX_REQUESTS = 10  # Máx requests LLM por IP por ventana
# Rutas a las que se aplica el rate limit del LLM (incluye el endpoint públ. de análisis)
_RATE_LIMITED_PATHS = {
    "/api/analisis",
    "/api/analizar/previa",
}

_ABUSE_WINDOW_SECS = 60
_ABUSE_MAX_AUTH = 20
_ABUSE_MAX_GEO = 60
_ABUSE_PATH_LIMITS = {
    "/api/auth/google": _ABUSE_MAX_AUTH,
    "/api/analizar/geocodificar": _ABUSE_MAX_GEO,
    "/api/analizar/buscar-direccion": _ABUSE_MAX_GEO,
}


class AbuseRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit por IP para login y geocoding (mitiga abuso de cuota Google/OAuth)."""

    def __init__(self, app):
        super().__init__(app)
        self._windows: dict[str, collections.deque] = collections.defaultdict(lambda: collections.deque())

    def _is_private_ip(self, ip: str) -> bool:
        return ip.startswith(("127.", "10.", "172.", "192.168.", "::1")) or ip == "testclient"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"
        # Normalizar paths con query
        for limited_path, max_req in _ABUSE_PATH_LIMITS.items():
            if path == limited_path or path.startswith(limited_path + "/"):
                client_ip = request.client.host if request.client else "unknown"
                if self._is_private_ip(client_ip):
                    break
                key = f"{limited_path}:{client_ip}"
                now = time.monotonic()
                window = self._windows[key]
                while window and now - window[0] > _ABUSE_WINDOW_SECS:
                    window.popleft()
                if len(window) >= max_req:
                    logger.warning("[RATE_LIMIT] IP %s bloqueada en %s", client_ip, limited_path)
                    return JSONResponse(
                        status_code=429,
                        content={
                            "status": "error",
                            "friendly_message": "Has realizado demasiadas solicitudes en poco tiempo.",
                            "suggested_action": f"Espera {_ABUSE_WINDOW_SECS} segundos e intenta de nuevo.",
                            "retry_after_seconds": _ABUSE_WINDOW_SECS,
                        },
                        headers={"Retry-After": str(_ABUSE_WINDOW_SECS)},
                    )
                window.append(now)
                break
        return await call_next(request)


class LLMRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware de rate limiting deslizante por IP para endpoints que invocan al LLM.
    Protege los créditos de Groq/Bedrock contra ataques de agotamiento de API.

    Implementa un sliding window de {_RATE_LIMIT_MAX_REQUESTS} requests en {_RATE_LIMIT_WINDOW_SECS}s
    por dirección IP. Las IPs privadas (127.x, 10.x, 172.x) quedan excluidas del límite
    para no afectar entornos de desarrollo local.
    """

    def __init__(self, app):
        super().__init__(app)
        # Diccionario IP -> deque de timestamps de requests recientes
        self._windows: dict[str, collections.deque] = collections.defaultdict(lambda: collections.deque())

    def _is_private_ip(self, ip: str) -> bool:
        """Excluye IPs privadas/loopback del rate limiting."""
        return ip.startswith(("127.", "10.", "172.", "192.168.", "::1")) or ip == "testclient"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Solo aplicar a rutas sensibles de LLM
        if request.method == "POST" and path in _RATE_LIMITED_PATHS:
            client_ip = request.client.host if request.client else "unknown"

            if not self._is_private_ip(client_ip):
                now = time.monotonic()
                window = self._windows[client_ip]

                # Limpiar timestamps fuera de la ventana
                while window and now - window[0] > _RATE_LIMIT_WINDOW_SECS:
                    window.popleft()

                if len(window) >= _RATE_LIMIT_MAX_REQUESTS:
                    logger.warning(
                        "[RATE_LIMIT] IP %s superó el límite de %d requests LLM en %ds. Request bloqueado.",
                        client_ip,
                        _RATE_LIMIT_MAX_REQUESTS,
                        _RATE_LIMIT_WINDOW_SECS,
                    )
                    return JSONResponse(
                        status_code=429,
                        content={
                            "status": "error",
                            "friendly_message": "Has realizado demasiadas consultas en poco tiempo.",
                            "suggested_action": (
                                f"Por favor espera {_RATE_LIMIT_WINDOW_SECS} segundos "
                                "antes de realizar una nueva consulta de análisis."
                            ),
                            "retry_after_seconds": _RATE_LIMIT_WINDOW_SECS,
                        },
                        headers={"Retry-After": str(_RATE_LIMIT_WINDOW_SECS)},
                    )

                window.append(now)

        return await call_next(request)


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
            transaction_id = f"err_aws_{uuid.uuid4().hex[:8]}"
            logger.exception(f"[{transaction_id}] CRITICAL: AWS SDK Error: {exc}")
            friendly = "Estamos experimentando una alta demanda en nuestro motor de análisis estratégico inteligente."
            action = (
                "Tu reporte cuantitativo está a salvo. Puedes intentar regenerar el análisis "
                "estratégico en unos minutos sin costo adicional."
            )
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
            transaction_id = f"err_net_{uuid.uuid4().hex[:8]}"
            logger.exception(f"[{transaction_id}] ERROR: External HTTP request failed: {exc}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "friendly_message": "No pudimos conectar con los servidores de mapas satelitales.",
                    "suggested_action": (
                        "El resto de la demografía del INEGI está lista. "
                        "Intenta consultar el mapa de nuevo en unos minutos."
                    ),
                    "transaction_id": transaction_id,
                },
            )
        except Exception as exc:
            from app.exceptions import UserFacingError

            if isinstance(exc, UserFacingError):
                transaction_id = f"err_usr_{uuid.uuid4().hex[:8]}"
                logger.warning("[%s] UserFacingError (middleware): %s", transaction_id, exc.message)
                body: dict = {
                    "status": "error",
                    "friendly_message": exc.message,
                    "transaction_id": transaction_id,
                }
                if exc.suggested_action:
                    body["suggested_action"] = exc.suggested_action
                return JSONResponse(status_code=exc.status_code, content=body)

            transaction_id = f"err_sys_{uuid.uuid4().hex[:8]}"
            logger.exception(f"[{transaction_id}] UNEXPECTED ERROR: {exc}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "friendly_message": "Ha surgido un inconveniente inesperado en la plataforma.",
                    "suggested_action": (
                        "No te preocupes; nuestro equipo técnico ha sido notificado automáticamente. "
                        "Por favor, intenta tu consulta en breve."
                    ),
                    "transaction_id": transaction_id,
                },
            )
