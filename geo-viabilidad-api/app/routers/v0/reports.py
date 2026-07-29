import logging

from fastapi import APIRouter, Query, status
from fastapi.responses import FileResponse

from app.core.deps import DbDep, UserDep
from app.exceptions import ForbiddenError
from app.schemas.v0.reports_schemas import ReportesPdfMetaResponse
from app.services.v0.reports.reports_service import (
    obtener_pdf_local_path,
    obtener_url_descarga_pdf,
)

logger = logging.getLogger("reports_router")

router = APIRouter(prefix="/api/reportes", tags=["Reportes"])


@router.get(
    "/pdf/{orden_id}",
    response_model=ReportesPdfMetaResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener URL de descarga del PDF",
    description=(
        "Si el informe ya está listo, devuelve JSON con `url_descarga` (enlace de corta vigencia "
        "con token firmado de un solo uso en almacenamiento local).\n\n"
        "Requiere Bearer/cookie y ownership de la orden."
    ),
)
def descargar_pdf(
    orden_id: int,
    db: DbDep,
    user: UserDep,
):
    logger.info("Petición de descarga de PDF para la orden %s por el usuario %s.", orden_id, user.cognito_user_id)
    resultado = obtener_url_descarga_pdf(
        orden_id=orden_id,
        cognito_user_id=user.cognito_user_id,
        roles=user.roles,
        db=db,
    )
    return ReportesPdfMetaResponse(
        status="success",
        **resultado.model_dump(),
        mensaje_seguridad=(
            "Este enlace es privado, de un solo uso y tiene una vigencia limitada "
            "de 10 minutos por ciberseguridad corporativa."
        ),
    )


@router.get(
    "/pdf/{orden_id}/descargar",
    response_class=FileResponse,
    status_code=status.HTTP_200_OK,
    summary="Descargar archivo PDF",
    description=(
        "Devuelve el binario PDF. Requiere query `token` firmado de un solo uso "
        "emitido por `GET /pdf/{orden_id}` (TTL ~10 min)."
    ),
    responses={
        200: {
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
            "description": "Archivo PDF del reporte.",
        }
    },
)
def descargar_pdf_archivo(
    orden_id: int,
    db: DbDep,
    token: str = Query(..., description="JWT de descarga de un solo uso"),
):
    if not token or not token.strip():
        raise ForbiddenError("Se requiere el token de descarga en la URL.")
    local_path, filename = obtener_pdf_local_path(
        orden_id,
        db,
        download_token=token.strip(),
    )
    return FileResponse(path=local_path, filename=filename, media_type="application/pdf")
