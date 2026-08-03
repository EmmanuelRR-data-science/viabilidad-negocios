"""Tokens firmados de un solo uso para descarga de PDF (TTL corto)."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import DOWNLOAD_TOKEN_TTL_SECONDS, SESSION_SECRET

logger = logging.getLogger("download_tokens")

DOWNLOAD_ISSUER = "geoviabilidad"
DOWNLOAD_TOKEN_TYPE = "download"

_used_lock = threading.Lock()
_used_jtis: dict[str, int] = {}


def _purge_used(now: int | None = None) -> None:
    ts = now if now is not None else int(time.time())
    expired = [j for j, exp in _used_jtis.items() if exp <= ts]
    for j in expired:
        _used_jtis.pop(j, None)


def crear_download_token(*, orden_id: int, cognito_user_id: str) -> tuple[str, int]:
    """Emite JWT de descarga. Devuelve `(token, validez_segundos)`."""
    now = datetime.now(UTC)
    ttl = int(DOWNLOAD_TOKEN_TTL_SECONDS)
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
    token = jwt.encode(payload, SESSION_SECRET, algorithm="HS256")
    return token, ttl


def verificar_download_token(token: str, *, orden_id: int, consume: bool = True) -> dict[str, Any]:
    """Valida token de descarga para `orden_id`. Si `consume`, marca jti como usado."""
    try:
        claims = jwt.decode(
            token,
            SESSION_SECRET,
            algorithms=["HS256"],
            issuer=DOWNLOAD_ISSUER,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.PyJWTError as err:
        logger.debug("Download token inválido: %s", err)
        raise ValueError("Enlace de descarga inválido o expirado.") from err

    if claims.get("typ") != DOWNLOAD_TOKEN_TYPE:
        raise ValueError("Enlace de descarga inválido.")
    if int(claims.get("orden_id", -1)) != int(orden_id):
        raise ValueError("El enlace de descarga no corresponde a esta orden.")

    jti = str(claims.get("jti") or "")
    exp = int(claims.get("exp") or 0)
    with _used_lock:
        _purge_used()
        if jti and jti in _used_jtis:
            raise ValueError("Este enlace de descarga ya fue utilizado.")
        if consume and jti:
            _used_jtis[jti] = exp

    return claims
