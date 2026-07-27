"""
conftest.py para tests/security/
Garantiza que el módulo de pruebas de seguridad sea independiente
de la base de datos y de la inicialización de FastAPI.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("DEV_MODE", "True")

# psycopg2 en Windows falla con home no-ASCII; no aplica en Linux/macOS.
if sys.platform == "win32":
    os.environ.setdefault("PGPASSFILE", r"C:\Users\Public\pgpass.conf")

# Asegurar que el root del proyecto está en el path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
