"""Lógica de negocio: autenticación Google Sign-In → sesión de aplicación."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.clients.v0.database import AppUsuario
from app.clients.v0.google.google_auth import google_auth_habilitado, verificar_id_token_google
from app.core.config import settings
from app.core.session_tokens import crear_session_token
from app.schemas.auth_schemas import AuthConfigResponse, AuthUserResponse, GoogleAuthResponse

logger = logging.getLogger("auth_service")


def obtener_config_auth() -> AuthConfigResponse:
    return AuthConfigResponse(
        enabled=google_auth_habilitado(),
        client_id=settings.GOOGLE_OAUTH_CLIENT_ID or None,
        public_app_url=settings.PUBLIC_APP_URL or None,
    )


def upsert_usuario_google(db: Session, idinfo: dict) -> AppUsuario:
    google_sub = str(idinfo["sub"])
    email = str(idinfo.get("email") or "").strip()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tu cuenta de Google no compartió correo electrónico. Usa otra cuenta o revisa permisos.",
        )

    nombre = (idinfo.get("name") or idinfo.get("given_name") or "").strip() or None
    avatar_url = (idinfo.get("picture") or "").strip() or None
    ahora = datetime.utcnow()

    usuario = db.query(AppUsuario).filter(AppUsuario.google_sub == google_sub).one_or_none()
    if usuario is None:
        usuario = AppUsuario(
            google_sub=google_sub,
            email=email,
            nombre=nombre,
            avatar_url=avatar_url,
            primera_sesion=ahora,
            ultima_sesion=ahora,
        )
        db.add(usuario)
        logger.info("Nuevo usuario Google registrado: %s (%s)", email, google_sub)
    else:
        usuario.email = email
        usuario.nombre = nombre or usuario.nombre
        usuario.avatar_url = avatar_url or usuario.avatar_url
        usuario.ultima_sesion = ahora
        logger.info("Usuario Google actualizado: %s", email)

    db.commit()
    db.refresh(usuario)
    return usuario


def autenticar_con_google(credential: str, db: Session) -> GoogleAuthResponse:
    """Valida el ID token de Google una sola vez y emite JWT de sesión de la app."""
    if not google_auth_habilitado():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticación con Google no configurada en el servidor.",
        )

    try:
        idinfo = verificar_id_token_google(credential)
    except ValueError as err:
        logger.warning("Token Google rechazado: %s", err)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión de Google inválida o expirada.",
        ) from err
    except Exception as err:
        logger.error("Error al verificar token Google: %s", err)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar la sesión de Google.",
        ) from err

    usuario = upsert_usuario_google(db, idinfo)
    access_token, expires_in = crear_session_token(
        google_sub=usuario.google_sub,
        email=usuario.email,
        nombre=usuario.nombre,
        roles=["user"],
    )
    return GoogleAuthResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in or settings.SESSION_TTL_SECONDS,
        user=AuthUserResponse(
            google_sub=usuario.google_sub,
            email=usuario.email,
            nombre=usuario.nombre,
            avatar_url=usuario.avatar_url,
        ),
    )
