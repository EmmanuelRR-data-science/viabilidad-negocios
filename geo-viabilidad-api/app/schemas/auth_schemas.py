"""Esquemas HTTP de autenticación."""

from pydantic import BaseModel, Field


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
