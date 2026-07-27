"""Verificación de credenciales de Google Sign-In (ID token).

Migrado desde clients/google_auth.py → clients/v0/google/ para política hot-path v0-only.
"""

from __future__ import annotations

import logging
from typing import Any

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import GOOGLE_OAUTH_CLIENT_ID

logger = logging.getLogger("google_auth")

_MOCK_TOKENS = frozenset({"mock-token", "mock-jwt-user", "mock-jwt-admin"})


def google_auth_habilitado() -> bool:
    return bool(GOOGLE_OAUTH_CLIENT_ID)


def es_token_mock(token: str | None) -> bool:
    return bool(token and token in _MOCK_TOKENS)


def verificar_id_token_google(token: str) -> dict[str, Any]:
    """Valida un ID token emitido por Google y devuelve los claims."""
    if not GOOGLE_OAUTH_CLIENT_ID:
        raise ValueError("GOOGLE_OAUTH_CLIENT_ID no configurado")
    idinfo = id_token.verify_oauth2_token(
        token,
        google_requests.Request(),
        GOOGLE_OAUTH_CLIENT_ID,
        clock_skew_in_seconds=120,
    )
    if idinfo.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError("Emisor del token no válido")
    if not idinfo.get("sub"):
        raise ValueError("Token sin identificador de usuario (sub)")
    return idinfo
