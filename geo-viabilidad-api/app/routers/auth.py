"""Router HTTP delgado: autenticación Google → sesión de aplicación."""

from __future__ import annotations

from fastapi import APIRouter, Header, Query, Request, Response

from app.core.config import settings
from app.core.deps import DbDep, UserDep
from app.core.session_tokens import cookie_kwargs, revoke_session_token
from app.schemas.auth_schemas import (
    AuthConfigResponse,
    AuthUserResponse,
    GoogleAuthRequest,
    GoogleAuthResponse,
    LogoutResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


def _wants_access_token_in_body(
    for_client: str | None,
    x_client: str | None,
) -> bool:
    flag = (for_client or "").strip().lower()
    header = (x_client or "").strip().lower()
    return flag == "swagger" or header == "swagger"


@router.get(
    "/config",
    response_model=AuthConfigResponse,
    summary="Configuración de autenticación",
    description=(
        "Indica si Google OAuth está habilitado, el `client_id` público para el front "
        "y la `public_app_url` configurada. No requiere Bearer."
    ),
)
def obtener_config_auth():
    return auth_service.obtener_config_auth()


@router.post(
    "/google",
    response_model=GoogleAuthResponse,
    summary="Intercambiar ID token de Google por sesión de app",
    description=(
        "Único endpoint que acepta el `credential` (ID token de Google). "
        "Valida el token, crea/actualiza el usuario y establece cookie HttpOnly `gv_session`.\n\n"
        "El SPA no recibe `access_token` en el body (solo cookie). "
        "Para Swagger usa `?for=swagger` o header `X-Client: swagger`."
    ),
)
def autenticar_con_google(
    payload: GoogleAuthRequest,
    response: Response,
    db: DbDep,
    for_client: str | None = Query(None, alias="for"),
    x_client: str | None = Header(None, alias="X-Client"),
):
    result = auth_service.autenticar_con_google(payload.credential, db)
    # Siempre setear cookie; el token completo vive en result.access_token antes de filtrar.
    raw_token = result.access_token
    if raw_token:
        response.set_cookie(value=raw_token, **cookie_kwargs())
    if not _wants_access_token_in_body(for_client, x_client):
        result.access_token = None
    return result


@router.get(
    "/me",
    response_model=AuthUserResponse,
    summary="Usuario de la sesión actual",
    description="Devuelve el perfil asociado a la cookie/Bearer de sesión de la app.",
)
def obtener_usuario_actual(user: UserDep):
    return AuthUserResponse(
        google_sub=user.cognito_user_id,
        email=user.email,
        nombre=user.nombre,
        avatar_url=None,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Cerrar sesión",
    description="Revoca el jti de la sesión (si aplica) y elimina la cookie HttpOnly.",
)
def cerrar_sesion(request: Request, response: Response):
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip() or token
    revoke_session_token(token)
    response.set_cookie(**cookie_kwargs(clear=True))
    return LogoutResponse(status="ok")
