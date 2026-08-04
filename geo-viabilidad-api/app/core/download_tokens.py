"""Tokens firmados de un solo uso para descarga de PDF (TTL corto)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import settings
from app.core.jti_store import InMemoryJtiStore

logger = logging.getLogger("download_tokens")

DOWNLOAD_ISSUER = "geoviabilidad"
DOWNLOAD_TOKEN_TYPE = "download"

_used_store = InMemoryJtiStore()


def crear_download_token(*, orden_id: int, cognito_user_id: str) -> tuple[str, int]:
    """Emite JWT de descarga. Devuelve `(token, validez_segundos)`."""
    now = datetime.now(UTC)
    ttl = int(settings.DOWNLOAD_TOKEN_TTL_SECONDS)
    exp_ts = int((now + timedelta(seconds=ttl)).timestamp())
    payload = {
        "iss": DOWNLOAD_ISSUER,
        "typ": DOWNLOAD_TOKEN_TYPE,
        "sub": cognito_user_id,
        "orden_id": int(orden_id),
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": exp_ts,
    }
    token = jwt.encode(payload, settings.SESSION_SECRET, algorithm="HS256")
    return token, ttl


def verificar_download_token(token: str, *, orden_id: int, consume: bool = True) -> dict[str, Any]:
    """Valida token de descarga para `orden_id`. Si `consume`, marca jti como usado."""
    try:
        claims = jwt.decode(
            token,
            settings.SESSION_SECRET,
            algorithms=["HS256"],
            issuer=DOWNLOAD_ISSUER,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.PyJWTError as err:
        logger.debug("Download token inválido: %s", err)
        raise ValueError("Enlace de descarga inválido.") from err

    if claims.get("typ") != DOWNLOAD_TOKEN_TYPE:
        raise ValueError("Enlace de descarga inválido.")
    if int(claims.get("orden_id", -1)) != int(orden_id):
        raise ValueError("Enlace de descarga inválido.")

    jti = str(claims.get("jti") or "")
    exp = int(claims.get("exp") or 0)

    if _used_store.is_consumed_or_mark(jti, exp, mark=consume):
        raise ValueError("Enlace de descarga inválido.")

    return claims
