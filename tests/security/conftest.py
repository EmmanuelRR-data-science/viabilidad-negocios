"""
conftest.py para tests/security/
Garantiza que el módulo de pruebas de seguridad sea independiente
de la base de datos y de la inicialización de FastAPI.
"""
import os
import sys
from pathlib import Path

# Asegurar que el root del proyecto está en el path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Forzar DEV_MODE para evitar conexiones reales a BD o AWS
os.environ.setdefault("DEV_MODE", "True")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
