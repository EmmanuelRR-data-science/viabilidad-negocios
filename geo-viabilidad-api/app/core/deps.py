"""Dependencias FastAPI tipadas (evita B008: call en defaults)."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.clients.v0.database import get_db
from app.core.security import UserContext, get_current_user

DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[UserContext, Depends(get_current_user)]
