"""Excepciones user-centric del panel admin."""

from __future__ import annotations


class AdminUserError(Exception):
    """Error orientado al operador del panel (mensaje en español)."""

    def __init__(self, message: str, *, suggested_action: str | None = None):
        self.message = message
        self.suggested_action = suggested_action
        super().__init__(message)


class DatabaseUnavailableError(AdminUserError):
    def __init__(self, technical: str | None = None):
        super().__init__(
            "No pudimos conectar con la base de datos en este momento.",
            suggested_action="Verifica que el servicio PostGIS esté en ejecución e intenta de nuevo.",
        )
        self.technical = technical


class IngestFailedError(AdminUserError):
    def __init__(self, message: str | None = None):
        super().__init__(
            message or "La ingesta no se pudo completar. Revisa el formato del archivo y los logs técnicos.",
            suggested_action="Confirma que el ZIP sea válido y que el esquema AGEB esté inicializado.",
        )


class SchemaInitError(AdminUserError):
    def __init__(self, message: str | None = None):
        super().__init__(
            message or "No se pudo inicializar o verificar el esquema de la base de datos.",
            suggested_action="Revisa permisos de la BD y vuelve a abrir la página de ingesta.",
        )
