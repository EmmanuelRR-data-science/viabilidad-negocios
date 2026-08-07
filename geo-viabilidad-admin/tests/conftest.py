"""pytest: panel admin Flask."""

import os
import sys
from pathlib import Path

os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("PAYMENTS_MODE", "mock")
os.environ.setdefault("PAYMENTS_MOCK", "true")

ADMIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ADMIN_ROOT.parent
DATA_PKG = REPO_ROOT / "geo-viabilidad-data"
if str(ADMIN_ROOT) not in sys.path:
    sys.path.insert(0, str(ADMIN_ROOT))
if str(DATA_PKG) not in sys.path:
    sys.path.insert(0, str(DATA_PKG))
