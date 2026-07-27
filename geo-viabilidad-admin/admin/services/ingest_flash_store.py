"""Almacén en memoria para resultados de ingesta (evita cookies de sesión gigantes)."""

from __future__ import annotations

import secrets
import time
from typing import Any

_MAX_ENTRIES = 20
_TTL_SECONDS = 3600
_store: dict[str, tuple[float, dict[str, Any]]] = {}


def stash_ingest_payload(payload: dict[str, Any]) -> str:
    _purge_expired()
    token = secrets.token_urlsafe(16)
    _store[token] = (time.time(), payload)
    while len(_store) > _MAX_ENTRIES:
        oldest = min(_store, key=lambda key: _store[key][0])
        _store.pop(oldest, None)
    return token


def pop_ingest_payload(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    _purge_expired()
    entry = _store.pop(token, None)
    if not entry:
        return None
    return entry[1]


def _purge_expired() -> None:
    now = time.time()
    expired = [key for key, (created, _payload) in _store.items() if now - created > _TTL_SECONDS]
    for key in expired:
        _store.pop(key, None)
