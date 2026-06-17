import logging

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import DEV_MODE

logger = logging.getLogger("auth")
security_scheme = HTTPBearer(auto_error=False)


class UserContext(BaseModel):
    """
    Contexto de usuario autenticado extraído de Amazon Cognito o del simulador.
    """

    cognito_user_id: str
    email: str
    roles: list[str] = ["user"]


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security_scheme)) -> UserContext:
    """
    Dependencia de FastAPI para obtener y validar el usuario actualmente firmado.
    Si DEV_MODE=True, admite tokens simulados o la falta de credenciales para facilitar pruebas.
    En producción, decodificará y validará el token JWT emitido por Amazon Cognito.
    """
    if DEV_MODE:
        # Modo Desarrollo: Simulación sin contacto con AWS Cognito
        logger.info("Modo Desarrollo Activo: Concediendo acceso de usuario simulado (Mock).")

        # Opcional: Si el usuario envía un token específico, lo registramos para pruebas
        token = credentials.credentials if credentials else "mock-token"

        # Retornamos un contexto de prueba con privilegios normales y administrador
        return UserContext(cognito_user_id="usr_mock_123", email="demo_sva@geoviabilidad.com", roles=["user", "admin"])

    # --- MODO PRODUCCIÓN (AWS Cognito Real) ---
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere un token de autenticación Bearer en la cabecera.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    logger.info(f"Procesando validación de firma para token: {token[:10]}...")
    try:
        # En producción (Fase de Cierre): Aquí implementaremos la decodificación dinámica
        # descargando las llaves públicas JWKs de:
        # https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json
        # Por ahora, si no está en DEV_MODE y no hay llaves reales levantadas, levantamos excepción
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Autenticación Cognito Real aún no configurada en este entorno.",
        )
    except Exception as e:
        logger.error(f"Falla al decodificar token JWT de Cognito: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso inválido o caducado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
