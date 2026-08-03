import logging
from typing import Annotated

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.clients.v0.google.google_auth import es_token_mock, google_auth_habilitado
from app.core.config import DEV_MODE, SESSION_COOKIE_NAME
from app.core.session_tokens import verificar_session_token

logger = logging.getLogger("auth")
security_scheme = HTTPBearer(auto_error=False)


class UserContext(BaseModel):
    """
    Contexto de usuario autenticado (sesión de app, mock de pruebas o legado DEV).
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


def _extraer_bearer_o_cookie(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    if credentials and credentials.credentials:
        return credentials.credentials
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    return None


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(security_scheme)] = None,
) -> UserContext:
    """
    Valida sesión de aplicación.

    Orden: Bearer de sesión / mock → cookie HttpOnly `gv_session`.
    El ID token de Google ya no se acepta en endpoints de negocio (solo en `/api/auth/google`).
    """
    token = _extraer_bearer_o_cookie(request, credentials)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación. Inicia sesión con Google.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Tokens mock solo en desarrollo local / demos. En producción (DEV_MODE=false) se rechazan.
    if es_token_mock(token):
        if DEV_MODE:
            return _contexto_mock(token)
        logger.warning("Se rechazó token mock con DEV_MODE=false.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación mock no disponible fuera de desarrollo.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = verificar_session_token(token)
    if claims:
        return UserContext(
            cognito_user_id=str(claims["sub"]),
            email=str(claims.get("email") or ""),
            nombre=(claims.get("name") or None),
            roles=list(claims.get("roles") or ["user"]),
        )

    # Rechazar ID tokens de Google u otros JWT ajenos en el hot path.
    if google_auth_habilitado() and token.count(".") == 2:
        logger.warning("Se rechazó un JWT que no es sesión de aplicación (posible ID token de Google).")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada. Vuelve a iniciar sesión con Google.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token de acceso inválido o caducado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
