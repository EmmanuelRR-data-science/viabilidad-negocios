import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.clients.v0.database import get_db
from app.core.security import UserContext, get_current_user
from app.services.v0.reports.reports_service import (
    obtener_pdf_local_path,
    obtener_url_descarga_pdf,
)

logger = logging.getLogger("reports_router")

router = APIRouter(prefix="/api/reportes", tags=["Reportes"])


@router.get("/pdf/{orden_id}", status_code=status.HTTP_200_OK)
def descargar_pdf(
    orden_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    logger.info("Petición de descarga de PDF para la orden %s por el usuario %s.", orden_id, user.cognito_user_id)
    resultado = obtener_url_descarga_pdf(
        orden_id=orden_id,
        cognito_user_id=user.cognito_user_id,
        roles=user.roles,
        db=db,
    )
    return {
        "status": "success",
        **resultado.model_dump(),
        "mensaje_seguridad": "Este enlace es privado y tiene una vigencia limitada de 10 minutos por ciberseguridad corporativa.",
    }


@router.get("/pdf/{orden_id}/descargar", status_code=status.HTTP_200_OK)
def descargar_pdf_archivo(orden_id: int, db: Session = Depends(get_db)):
    """Descarga directamente el archivo PDF local en modo desarrollo."""
    local_path, filename = obtener_pdf_local_path(orden_id, db)
    return FileResponse(path=local_path, filename=filename, media_type="application/pdf")
