"""DEPRECATED — use app.clients.v0.besttime instead.

This flat module is retained only for backward compatibility with tests.
Hot-path code MUST import from ``app.clients.v0.besttime``.
"""

from app.clients.v0.besttime.besttime_client_processed import (  # noqa: F401
    construir_filas_horas_pico,
    obtener_afluencia,
    obtener_afluencia_simulada,
)
