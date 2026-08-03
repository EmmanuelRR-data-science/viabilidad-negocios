"""Excepciones user-centric de la API."""

from app.exceptions.base import (
    ExternalDependencyError,
    ForbiddenError,
    NotFoundError,
    PaymentRequiredError,
    UserFacingError,
    ValidationUserError,
)

__all__ = [
    "ExternalDependencyError",
    "ForbiddenError",
    "NotFoundError",
    "PaymentRequiredError",
    "UserFacingError",
    "ValidationUserError",
]
