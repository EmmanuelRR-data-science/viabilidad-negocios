import logging

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import DEV_MODE, GOOGLE_OAUTH_CLIENT_ID
from app.google_auth import es_token_mock, google_auth_habilitado, verificar_id_token_google

logger = logging.getLogger("auth")
security_scheme = HTTPBearer(auto_error=False)


class UserContext(BaseModel):
    """
    Contexto de usuario autenticado extraído de Google Sign-In o del simulador de pruebas.
    """

    cognito_user_id: str
    email: str
    nombre: str | None = None
    roles: list[str] = ["user"]


def _contexto_mock(token: str | None) -> UserContext:
    roles = ["user", "admin"] if token == "mock-jwt-admin" else ["user"]
    return UserContext(
        cognito_user_id="usr_mock_123",
        email="demo_sva@geoviabilidad.com",
        nombre="Usuario de prueba",
        roles=roles,
    )


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security_scheme)) -> UserContext:
    """
    Dependencia de FastAPI para obtener y validar el usuario actualmente firmado.
    Prioridad: token mock (tests) → ID token Google → fallback DEV sin OAuth configurado.
    """
    token = credentials.credentials if credentials else None

    if es_token_mock(token):
        return _contexto_mock(token)

    if token and google_auth_habilitado():
        try:
            idinfo = verificar_id_token_google(token)
            return UserContext(
                cognito_user_id=str(idinfo["sub"]),
                email=str(idinfo.get("email") or ""),
                nombre=(idinfo.get("name") or idinfo.get("given_name") or None),
                roles=["user"],
            )
        except Exception as err:
            logger.warning("Bearer token rechazado: %s", err)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de acceso inválido o caducado. Vuelve a iniciar sesión con Google.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from err

    if DEV_MODE and not GOOGLE_OAUTH_CLIENT_ID:
        logger.info("Modo desarrollo sin Google OAuth: acceso simulado concedido.")
        return _contexto_mock(token)

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación con Google.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token de acceso inválido o caducado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
