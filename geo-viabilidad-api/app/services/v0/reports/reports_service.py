from __future__ import annotations

import logging
import os
import re

from sqlalchemy.orm import Session

from app.clients.v0.database import OrdenPago
from app.clients.v0.s3.s3_client_processed import obtener_url_descarga
from app.core.config import DEV_MODE, LOCAL_REPORTS_DIR, REPORTS_LOCAL_STORAGE, S3_REPORTS_BUCKET
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

    En modo local se devuelve una ruta relativa para que el cliente use el origen
    de la página (evita Mixed Content detrás de ngrok/proxies).
    """
    orden = db.query(OrdenPago).filter(OrdenPago.id == orden_id).first()
    if not orden:
        raise OrdenNoEncontradaError(f"Orden {orden_id} no encontrada.")

    # Validar permisos
    if orden.cognito_user_id != cognito_user_id and "admin" not in roles:
        raise AccesoNoAutorizadoError("No tienes autorización para descargar este reporte.")

    # Validar estado de pago
    if orden.estado_pago != "approved":
        raise PagoNoAcreditadoError("El análisis está pendiente de pago o procesamiento.")

    # Validar disponibilidad del PDF
    if not orden.s3_key_reporte:
        raise ReporteNoDisponibleError("El reporte PDF aún se encuentra en proceso de compilación.")

    filename = _construir_nombre_archivo(orden.rubro)

    # Determinar si usamos almacenamiento local (desarrollo/tests) o S3.
    # Ruta relativa por defecto: el frontend la resuelve con window.location.origin.
    if REPORTS_LOCAL_STORAGE or DEV_MODE:
        logger.info("[REPORTS SERVICE] Retornando URL de descarga directa local.")
        url = ruta_descarga_local or f"/api/reportes/pdf/{orden.id}/descargar"
        validez = 600
    else:
        logger.info("[REPORTS SERVICE] Generando URL presignada de S3.")
        descarga = obtener_url_descarga(S3_REPORTS_BUCKET, orden.s3_key_reporte, filename)
        url = descarga.url
        validez = descarga.validez_segundos

    return DescargaPDFResponse(
        url_descarga=url,
        validez_segundos=validez,
        orden_id=orden.id,
        checkout_id=orden.checkout_id or "",
    )


def obtener_pdf_local_path(orden_id: int, db: Session) -> tuple[str, str]:
    """Resuelve la ruta local del PDF para descarga directa (modo desarrollo).

    Returns:
        Tupla (ruta_absoluta, nombre_archivo_descarga).

    Raises:
        ValidationUserError: si el modo local no está habilitado.
        OrdenNoEncontradaError: si la orden no existe.
        ValidationUserError: si el pago no fue aprobado o el archivo no existe.
    """
    if not REPORTS_LOCAL_STORAGE:
        raise ValidationUserError(
            "La descarga directa local solo está disponible con REPORTS_LOCAL_STORAGE.",
        )

    orden = db.query(OrdenPago).filter(OrdenPago.id == orden_id).first()
    if not orden:
        raise OrdenNoEncontradaError()

    if orden.estado_pago != "approved":
        raise ValidationUserError(
            "El análisis correspondiente no ha sido aprobado ni pagado.",
        )

    rubro_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", orden.rubro.lower()).strip("_")
    local_pdf_path = f"{LOCAL_REPORTS_DIR}/{orden.checkout_id}_reporte_{rubro_slug}.pdf"

    if not os.path.exists(local_pdf_path):
        raise NotFoundError(
            "El archivo PDF del reporte no se encuentra disponible localmente.",
        )

    filename = f"Reporte_Viabilidad_{rubro_slug}.pdf"
    return local_pdf_path, filename
