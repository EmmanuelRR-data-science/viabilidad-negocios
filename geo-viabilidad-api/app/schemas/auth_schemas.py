"""Esquemas HTTP de autenticación."""

from pydantic import BaseModel, Field


class GoogleAuthRequest(BaseModel):
    credential: str = Field(
        ...,
        min_length=20,
        description="ID token JWT de Google Identity Services (solo se usa en este intercambio).",
    )


class AuthUserResponse(BaseModel):
    google_sub: str
    email: str
    nombre: str | None = None
    avatar_url: str | None = None


class GoogleAuthResponse(BaseModel):
    """Sesión de aplicación tras intercambiar el ID token de Google.

    Para el SPA la credencial es la cookie HttpOnly. `access_token` solo se incluye
    cuando el cliente pide modo Swagger (`?for=swagger` o header `X-Client: swagger`).
    """

    access_token: str | None = Field(
        None,
        description="JWT de sesión (solo para Swagger/API clients). El SPA usa cookie HttpOnly.",
    )
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Vigencia de la sesión en segundos.")
    user: AuthUserResponse


class AuthConfigResponse(BaseModel):
    enabled: bool
    client_id: str | None = None
    public_app_url: str | None = None


class LogoutResponse(BaseModel):
    status: str = "ok"
