"""Métricas agregadas para el dashboard administrativo."""

from __future__ import annotations

from admin.clients.db import session_scope
from admin.clients.metrics_client import AdminMetricsRow, query_admin_metrics

# Alias público estable para plantillas/tests
AdminMetrics = AdminMetricsRow


def fetch_admin_metrics(db=None) -> AdminMetrics:
    """Si se pasa ``db`` (tests legacy), lo usa; si no, abre sesión vía clients."""
    if db is not None:
        return query_admin_metrics(db)
    with session_scope() as session:
        return query_admin_metrics(session)
