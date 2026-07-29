"""Emisión/verificación de JWT de sesión y revocación por jti."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import SESSION_COOKIE_NAME, SESSION_SECRET, SESSION_TTL_SECONDS

logger = logging.getLogger("session_tokens")

SESSION_ISSUER = "geoviabilidad"
SESSION_TOKEN_TYPE = "session"

_revoked_lock = threading.Lock()
# jti -> unix exp (limpiamos entradas vencidas al consultar)
_revoked_jtis: dict[str, int] = {}


def _purge_revoked(now: int | None = None) -> None:
    ts = now if now is not None else int(time.time())
    expired = [j for j, exp in _revoked_jtis.items() if exp <= ts]
    for j in expired:
        _revoked_jtis.pop(j, None)


def revoke_jti(jti: str, exp: int) -> None:
    if not jti:
        return
    with _revoked_lock:
        _purge_revoked()
        _revoked_jtis[jti] = int(exp)


def is_jti_revoked(jti: str) -> bool:
    if not jti:
        return False
    with _revoked_lock:
        _purge_revoked()
        return jti in _revoked_jtis


def crear_session_token(
    *,
    google_sub: str,
    email: str,
    nombre: str | None = None,
    roles: list[str] | None = None,
) -> tuple[str, int]:
    """Devuelve `(token, expires_in_seconds)` firmado con SESSION_SECRET."""
    now = datetime.now(UTC)
    expires_in = int(SESSION_TTL_SECONDS)
    exp_ts = int((now + timedelta(seconds=expires_in)).timestamp())
    payload = {
        "iss": SESSION_ISSUER,
        "typ": SESSION_TOKEN_TYPE,
        "sub": google_sub,
        "email": email,
        "name": nombre,
        "roles": roles or ["user"],
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": exp_ts,
    }
    token = jwt.encode(payload, SESSION_SECRET, algorithm="HS256")
    return token, expires_in


def verificar_session_token(token: str) -> dict[str, Any] | None:
    """Valida un JWT de sesión. Devuelve claims o None si no es sesión válida."""
    try:
        claims = jwt.decode(
            token,
            SESSION_SECRET,
            algorithms=["HS256"],
            issuer=SESSION_ISSUER,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.PyJWTError as err:
        logger.debug("JWT de sesión rechazado: %s", err)
        return None

    if claims.get("typ") != SESSION_TOKEN_TYPE:
        return None
    jti = str(claims.get("jti") or "")
    if jti and is_jti_revoked(jti):
        logger.info("JWT de sesión revocado (jti=%s).", jti)
        return None
    return claims


def revoke_session_token(token: str | None) -> None:
    """Revoca un JWT de sesión (logout) hasta su exp natural."""
    if not token:
        return
    claims = verificar_session_token(token)
    if not claims:
        # Puede estar ya inválido; intentar decode sin chequear revoke
        try:
            claims = jwt.decode(
                token,
                SESSION_SECRET,
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
        except jwt.PyJWTError:
            return
    jti = str(claims.get("jti") or "")
    exp = int(claims.get("exp") or (time.time() + SESSION_TTL_SECONDS))
    revoke_jti(jti, exp)


def cookie_kwargs(*, clear: bool = False) -> dict[str, Any]:
    """Parámetros comunes para set_cookie / delete_cookie."""
    from app.core.config import DEV_MODE, PUBLIC_APP_URL

    secure = (not DEV_MODE) or (PUBLIC_APP_URL or "").startswith("https")
    base: dict[str, Any] = {
        "key": SESSION_COOKIE_NAME,
        "httponly": True,
        "secure": secure,
        "samesite": "lax",
        "path": "/",
    }
    if clear:
        base["value"] = ""
        base["max_age"] = 0
    else:
        base["max_age"] = int(SESSION_TTL_SECONDS)
    return base
