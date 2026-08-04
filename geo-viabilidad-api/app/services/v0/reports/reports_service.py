from __future__ import annotations

import logging
import os
import re

from sqlalchemy.orm import Session

from app.clients.v0.database import OrdenPago
from app.clients.v0.s3.s3_client_processed import obtener_url_descarga
from app.core.config import settings
from app.core.download_tokens import crear_download_token, verificar_download_token
from app.exceptions import ForbiddenError, NotFoundError, PaymentRequiredError, ValidationUserError
from app.schemas.v0.reports_schemas import DescargaPDFResponse

logger = logging.getLogger("reports_service")


class OrdenNoEncontradaError(NotFoundError):
    def __init__(self, message: str = "La orden de análisis comercial solicitada no existe."):
        super().__init__(message)


class AccesoNoAutorizadoError(ForbiddenError):
    def __init__(self, message: str = "No tienes autorización para acceder a este reporte comercial."):
        super().__init__(message)


class PagoNoAcreditadoError(PaymentRequiredError):
    def __init__(self, message: str = "El análisis está pendiente de pago o procesamiento."):
        super().__init__(message)


class ReporteNoDisponibleError(ValidationUserError):
    def __init__(self, message: str = "El reporte PDF aún se encuentra en proceso de compilación."):
        super().__init__(message, status_code=422)


def _construir_nombre_archivo(rubro: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", rubro.lower()).strip("_")
    return f"Reporte_Viabilidad_{slug}.pdf"


def obtener_url_descarga_pdf(
    orden_id: int,
    cognito_user_id: str,
    roles: list[str],
    db: Session,
    *,
    ruta_descarga_local: str | None = None,
) -> DescargaPDFResponse:
    """Valida la orden, autentica propiedad/roles, y construye la URL de descarga segura.

    En modo local se emite un token firmado de un solo uso (TTL corto) en la query.
    """
    orden = db.query(OrdenPago).filter(OrdenPago.id == orden_id).first()
    if not orden:
        raise OrdenNoEncontradaError(f"Orden {orden_id} no encontrada.")

    if orden.cognito_user_id != cognito_user_id and "admin" not in roles:
        raise AccesoNoAutorizadoError("No tienes autorización para descargar este reporte.")

    if orden.estado_pago != "approved":
        raise PagoNoAcreditadoError("El análisis está pendiente de pago o procesamiento.")

    if not orden.s3_key_reporte:
        raise ReporteNoDisponibleError("El reporte PDF aún se encuentra en proceso de compilación.")

    filename = _construir_nombre_archivo(orden.rubro)

    if settings.REPORTS_LOCAL_STORAGE or settings.DEV_MODE:
        token, validez = crear_download_token(orden_id=orden.id, cognito_user_id=cognito_user_id)
        if ruta_descarga_local:
            url = ruta_descarga_local
        else:
            url = f"/api/reportes/pdf/{orden.id}/descargar?token={token}"
        logger.info("[REPORTS SERVICE] URL local con token de descarga (TTL=%ss).", validez)
    else:
        logger.info("[REPORTS SERVICE] Generando URL presignada de S3.")
        descarga = obtener_url_descarga(settings.S3_REPORTS_BUCKET, orden.s3_key_reporte, filename)
        url = descarga.url
        validez = descarga.validez_segundos

    return DescargaPDFResponse(
        url_descarga=url,
        validez_segundos=validez,
        orden_id=orden.id,
        checkout_id=orden.checkout_id or "",
    )


def obtener_pdf_local_path(
    orden_id: int,
    db: Session,
    *,
    cognito_user_id: str | None = None,
    roles: list[str] | None = None,
    download_token: str | None = None,
) -> tuple[str, str]:
    """Resuelve la ruta local del PDF.

    Autorización: token de descarga firmado (preferente) o sesión + ownership.
    """
    if not settings.REPORTS_LOCAL_STORAGE:
        raise ValidationUserError(
            "La descarga directa local solo está disponible con settings.REPORTS_LOCAL_STORAGE.",
        )

    token_sub: str | None = None
    if download_token:
        try:
            claims = verificar_download_token(download_token, orden_id=orden_id, consume=True)
            token_sub = str(claims["sub"])
        except ValueError as err:
            raise AccesoNoAutorizadoError(str(err)) from err

    orden = db.query(OrdenPago).filter(OrdenPago.id == orden_id).first()
    if not orden:
        raise OrdenNoEncontradaError()

    if token_sub:
        if orden.cognito_user_id != token_sub and not (roles and "admin" in roles):
            raise AccesoNoAutorizadoError("No tienes autorización para descargar este reporte.")
    else:
        if not cognito_user_id:
            raise AccesoNoAutorizadoError("Se requiere un enlace de descarga válido o iniciar sesión.")
        if orden.cognito_user_id != cognito_user_id and "admin" not in (roles or []):
            raise AccesoNoAutorizadoError("No tienes autorización para descargar este reporte.")

    if orden.estado_pago != "approved":
        raise ValidationUserError(
            "El análisis correspondiente no ha sido aprobado ni pagado.",
        )

    rubro_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", orden.rubro.lower()).strip("_")
    local_pdf_path = f"{settings.LOCAL_REPORTS_DIR}/{orden.checkout_id}_reporte_{rubro_slug}.pdf"

    if not os.path.exists(local_pdf_path):
        raise NotFoundError(
            "El archivo PDF del reporte no se encuentra disponible localmente.",
        )

    filename = f"Reporte_Viabilidad_{rubro_slug}.pdf"
    return local_pdf_path, filename
