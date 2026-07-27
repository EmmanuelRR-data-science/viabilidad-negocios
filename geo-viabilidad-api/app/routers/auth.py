"""Router HTTP delgado: autenticación Google."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.clients.v0.database import get_db
from app.schemas.auth_schemas import AuthConfigResponse, GoogleAuthRequest, GoogleAuthResponse
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.get("/config", response_model=AuthConfigResponse)
def obtener_config_auth():
    return auth_service.obtener_config_auth()


@router.post("/google", response_model=GoogleAuthResponse)
def autenticar_con_google(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    return auth_service.autenticar_con_google(payload.credential, db)
