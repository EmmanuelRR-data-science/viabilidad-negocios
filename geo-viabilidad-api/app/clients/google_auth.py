"""DEPRECATED — use app.clients.v0.google.google_auth instead.

This flat module is retained only for backward compatibility.
Hot-path code MUST import from ``app.clients.v0.google.google_auth``.
"""

from app.clients.v0.google.google_auth import (  # noqa: F401
    es_token_mock,
    google_auth_habilitado,
    verificar_id_token_google,
)
