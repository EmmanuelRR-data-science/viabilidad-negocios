"""Rutas de autenticación con Google Sign-In."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import GOOGLE_OAUTH_CLIENT_ID, PUBLIC_APP_URL
from app.database import get_db
from app.google_auth import google_auth_habilitado, verificar_id_token_google
from app.models import AppUsuario

logger = logging.getLogger("routes_auth")

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., min_length=20, description="ID token JWT devuelto por Google Identity Services")


class AuthUserResponse(BaseModel):
    google_sub: str
    email: str
    nombre: str | None = None
    avatar_url: str | None = None


class GoogleAuthResponse(BaseModel):
    token: str
    user: AuthUserResponse


class AuthConfigResponse(BaseModel):
    enabled: bool
    client_id: str | None = None
    public_app_url: str | None = None


def _upsert_usuario(db: Session, idinfo: dict) -> AppUsuario:
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


@router.get("/config", response_model=AuthConfigResponse)
def obtener_config_auth():
    """Expone el Client ID público de Google para el frontend (GIS)."""
    return AuthConfigResponse(
        enabled=google_auth_habilitado(),
        client_id=GOOGLE_OAUTH_CLIENT_ID or None,
        public_app_url=PUBLIC_APP_URL or None,
    )


@router.post("/google", response_model=GoogleAuthResponse)
def autenticar_con_google(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Verifica el ID token de Google, persiste/actualiza el usuario y devuelve el perfil."""
    if not google_auth_habilitado():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticación con Google no configurada en el servidor.",
        )

    try:
        idinfo = verificar_id_token_google(payload.credential)
    except ValueError as err:
        logger.warning("Token Google rechazado: %s", err)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión de Google inválida o expirada.") from err
    except Exception as err:
        logger.error("Error al verificar token Google: %s", err)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar la sesión de Google.",
        ) from err

    usuario = _upsert_usuario(db, idinfo)
    return GoogleAuthResponse(
        token=payload.credential,
        user=AuthUserResponse(
            google_sub=usuario.google_sub,
            email=usuario.email,
            nombre=usuario.nombre,
            avatar_url=usuario.avatar_url,
        ),
    )
