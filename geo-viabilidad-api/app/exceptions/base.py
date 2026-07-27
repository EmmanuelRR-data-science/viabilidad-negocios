"""Excepciones user-centric base para toda la API."""

from __future__ import annotations


class UserFacingError(Exception):
    """Base para errores que se traducen en respuestas HTTP amigables."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str = "Ha ocurrido un error inesperado.",
        *,
        suggested_action: str | None = None,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        self.message = message
        self.suggested_action = suggested_action
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        super().__init__(message)


class NotFoundError(UserFacingError):
    status_code = 404
    code = "not_found"

    def __init__(
        self,
        message: str = "El recurso solicitado no existe.",
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)


class PaymentRequiredError(UserFacingError):
    status_code = 402
    code = "payment_required"

    def __init__(
        self,
        message: str = "El análisis está pendiente de pago o procesamiento.",
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)


class ForbiddenError(UserFacingError):
    status_code = 403
    code = "forbidden"

    def __init__(
        self,
        message: str = "No tienes autorización para acceder a este recurso.",
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)


class ExternalDependencyError(UserFacingError):
    status_code = 502
    code = "external_dependency"

    def __init__(
        self,
        message: str = "Uno de nuestros proveedores externos no respondió a tiempo.",
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)


class ValidationUserError(UserFacingError):
    status_code = 400
    code = "validation_error"

    def __init__(
        self,
        message: str = "Los datos proporcionados no son válidos.",
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
