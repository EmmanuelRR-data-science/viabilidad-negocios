import logging

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.clients.v0.database import get_db
from app.core.security import UserContext, get_current_user
from app.exceptions import ValidationUserError
from app.schemas.v0.analytics_schemas import SugerirAliadosRequest
from app.services.v0.analytics.analytics_service import (
    buscar_direccion_service,
    geocodificar_service,
    obtener_resultado_reporte,
    obtener_vista_previa_service,
    sugerir_aliados_service,
)

logger = logging.getLogger("analytics_router")

router = APIRouter(prefix="/api/analizar", tags=["Motor Analítico e INEGI"])


@router.post("/aliados/sugerir", status_code=status.HTTP_200_OK)
def sugerir_aliados_guiados(
    body: SugerirAliadosRequest,
    user: UserContext = Depends(get_current_user),
):
    """Motor de sugerencias para el cuestionario guiado."""
    _ = user
    return sugerir_aliados_service(body)


@router.get("/geocodificar", status_code=status.HTTP_200_OK)
def geocodificar_coordenadas(lat: float, lng: float):
    """Geocodificación Inversa: Convierte lat/lng en dirección mexicana."""
    return geocodificar_service(lat, lng)


@router.post("/previa", status_code=status.HTTP_200_OK)
async def obtener_vista_previa_gratuita(
    lat: float,
    lng: float,
    radio_metros: int,
    rubro: str,
    request: Request,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Vista Previa Gratuita: Retorna conteos e indicadores del INEGI."""
    logger.info("Generando Vista Previa Gratuita para usuario %s", user.cognito_user_id)

    competidores_sel = None
    aliados_sel = None
    intenciones = None
    competidores_adicionales = None
    aliados_adicionales = None
    modo_aliados = "automatico"
    config_guiada = None
    try:
        body = await request.json()
        competidores_sel = body.get("competidores_seleccionados")
        aliados_sel = body.get("aliados_seleccionados")
        intenciones = body.get("intenciones")
        competidores_adicionales = body.get("competidores_adicionales")
        aliados_adicionales = body.get("aliados_adicionales")
        modo_aliados = (body.get("modo_analisis_aliados") or "automatico").lower()
        config_guiada = body.get("config_aliados_guiados")
        if modo_aliados == "guiado" and config_guiada:
            aliados_sel = config_guiada.get("atractores_confirmados")
    except Exception:
        pass

    return obtener_vista_previa_service(
        db,
        lat,
        lng,
        radio_metros,
        rubro,
        competidores_sel=competidores_sel,
        aliados_sel=aliados_sel,
        intenciones=intenciones,
        competidores_adicionales=competidores_adicionales,
        aliados_adicionales=aliados_adicionales,
        modo_aliados=modo_aliados,
        config_guiada=config_guiada,
    )


@router.get("/resultado/{orden_id}", status_code=status.HTTP_200_OK)
def obtener_resultado_analisis(
    orden_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Obtiene el reporte completo delegando toda la lógica al servicio."""
    return obtener_resultado_reporte(
        orden_id=orden_id,
        cognito_user_id=user.cognito_user_id,
        roles=user.roles,
        db=db,
    )


@router.get("/buscar-direccion", status_code=status.HTTP_200_OK)
def buscar_direccion(direccion: str):
    """Geocodificación directa por texto."""
    direccion_query = direccion.strip() if direccion else ""
    if not direccion_query:
        raise ValidationUserError("La dirección o palabra de búsqueda no puede estar vacía.")
    return buscar_direccion_service(direccion_query)


@router.get("/debug/cuantitativo", status_code=status.HTTP_200_OK, include_in_schema=True)
def debug_cuantitativo(
    lat: float,
    lng: float,
    radio_metros: int = 1000,
    rubro: str = "cafeteria",
    tier: str = "premium",
    db: Session = Depends(get_db),
):
    """DEV_MODE only — dump cuantitativo JSON sin FODA/LLM. No bypassa PDF pagado."""
    from app.core.config import DEV_MODE

    if not DEV_MODE:
        raise ValidationUserError("Este endpoint solo está disponible en modo desarrollo (DEV_MODE=true).")
    from app.services.v0.analytics.analytics_service import procesar_calculo_analitico

    resultado = procesar_calculo_analitico(db=db, lat=lat, lng=lng, radio=radio_metros, rubro=rubro, tier=tier)
    return {"status": "debug", "nota": "Solo métricas cuantitativas, sin FODA ni PDF.", "metricas": resultado}
