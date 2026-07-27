"""Configuración pytest para la API."""

import os
import sys

os.environ["DEV_MODE"] = "true"
os.environ["PAYMENTS_MOCK"] = "true"
os.environ["REPORTS_LOCAL_STORAGE"] = "true"
os.environ["GOOGLE_OAUTH_CLIENT_ID"] = ""

# psycopg2 en Windows falla con home no-ASCII; no aplica en Linux/macOS.
if sys.platform == "win32":
    os.environ.setdefault("PGPASSFILE", r"C:\Users\Public\pgpass.conf")

import psycopg2

original_connect = psycopg2.connect


def mock_connect(*args, **kwargs):
    import sys as _sys

    _sys.stdout.write(f"DEBUG PSYCOPG2 CONNECT: args={args} kwargs={kwargs}\n")
    _sys.stdout.flush()
    return original_connect(*args, **kwargs)


psycopg2.connect = mock_connect
