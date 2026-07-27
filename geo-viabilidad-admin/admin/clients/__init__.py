"""Facade de clients admin."""

from admin.clients.db import get_engine, session_scope
from admin.clients.metrics_client import AdminMetricsRow, query_admin_metrics

__all__ = [
    "AdminMetricsRow",
    "get_engine",
    "query_admin_metrics",
    "session_scope",
]
