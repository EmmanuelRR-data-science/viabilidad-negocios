"""Cliente de sesión/engine — único punto de acceso a geo_viabilidad_data.database desde admin."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from geo_viabilidad_data.database import SessionLocal, engine
from sqlalchemy.orm import Session


def get_engine():
    return engine


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
