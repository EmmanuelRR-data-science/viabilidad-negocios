import logging

from fastapi import APIRouter, Request, status

from app.core.deps import DbDep, UserDep
from app.exceptions import ValidationUserError
from app.schemas.v0.analytics_schemas import (
    BuscarDireccionResponse,
    DebugCuantitativoResponse,
    GeocodificarResponse,
    ResultadoAnalisisResponse,
    SugerirAliadosRequest,
    SugerirAliadosResponse,
    VistaPreviaResponse,
)
from app.services.v0.analytics.analytics_service import (
    buscar_direccion_service,
    geocodificar_service,
    obtener_resultado_reporte,
    obtener_vista_previa_service,
    sugerir_aliados_service,
)

logger = logging.getLogger("analytics_router")


router = APIRouter(prefix="/api/analizar", tags=["Motor Analítico e INEGI"])


@router.post(
    "/aliados/sugerir",
    response_model=SugerirAliadosResponse,
    status_code=status.HTTP_200_OK,
    summary="Sugerir aliados (modo guiado)",
    description=(
        "Resuelve atractores/aliados a partir del cuestionario guiado (perfil de cliente "
        "y horarios pico). Requiere autenticación Bearer."
    ),
)
def sugerir_aliados_guiados(
    body: SugerirAliadosRequest,
    user: UserDep,
):
    _ = user

    return sugerir_aliados_service(body)


@router.get(
    "/geocodificar",
    response_model=GeocodificarResponse,
    status_code=status.HTTP_200_OK,
    summary="Geocodificación inversa",
    description=(
        "Convierte coordenadas (`lat`, `lng`) en una dirección estructurada vía Google Geocoding. "
        "Público (necesario para el mapa antes del login); protegido con rate limit por IP."
    ),
)
def geocodificar_coordenadas(lat: float, lng: float):
    return geocodificar_service(lat, lng)


@router.post(
    "/previa",
    response_model=VistaPreviaResponse,
    status_code=status.HTTP_200_OK,
    summary="Vista previa gratuita del análisis",
    description=(
        "Ejecuta el motor cuantitativo (INEGI/PostGIS + Places) y devuelve indicadores "
        "de la zona **sin generar PDF**.\n\n"
        "**Query:** `lat`, `lng`, `radio_metros`, `rubro`.\n"
        "**Body JSON opcional:** `competidores_seleccionados`, `aliados_seleccionados`, "
        "`intenciones`, `competidores_adicionales`, `aliados_adicionales`, "
        "`modo_analisis_aliados`, `config_aliados_guiados`.\n\n"
        "Requiere Bearer (sesión real; `mock-token` solo con `settings.DEV_MODE=true`)."
    ),
)
async def obtener_vista_previa_gratuita(
    lat: float,
    lng: float,
    radio_metros: int,
    rubro: str,
    request: Request,
    db: DbDep,
    user: UserDep,
):
    logger.info("Generando Vista Previa Gratuita para usuario %s", user.cognito_user_id)

    competidores_sel = None

    aliados_sel = None

    
    competidores_adicionales = None

    aliados_adicionales = None

    modo_aliados = "automatico"

    config_guiada = None

    try:
        body = await request.json()

        competidores_sel = body.get("competidores_seleccionados")

        aliados_sel = body.get("aliados_seleccionados")

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
        competidores_adicionales=competidores_adicionales,
        aliados_adicionales=aliados_adicionales,
        modo_aliados=modo_aliados,
        config_guiada=config_guiada,
    )


@router.get(
    "/resultado/{orden_id}",
    response_model=ResultadoAnalisisResponse,
    status_code=status.HTTP_200_OK,
    summary="Resultado completo de una orden",
    description=(
        "Devuelve métricas y análisis estratégico (FODA / respaldo) de una orden **ya pagada** "
        "y procesada. Requiere Bearer y ownership de la orden (o rol admin)."
    ),
)
def obtener_resultado_analisis(
    orden_id: int,
    db: DbDep,
    user: UserDep,
):
    return obtener_resultado_reporte(
        orden_id=orden_id,
        cognito_user_id=user.cognito_user_id,
        roles=user.roles,
        db=db,
    )


@router.get(
    "/buscar-direccion",
    response_model=BuscarDireccionResponse,
    status_code=status.HTTP_200_OK,
    summary="Buscar coordenadas por dirección",
    description=(
        "Geocodificación directa: texto libre → lista de candidatos con lat/lng "
        "(restringido a México). Público para el buscador del mapa; rate limit por IP."
    ),
)
def buscar_direccion(direccion: str):
    direccion_query = direccion.strip() if direccion else ""
    if not direccion_query:
        raise ValidationUserError("La dirección o palabra de búsqueda no puede estar vacía.")
    return buscar_direccion_service(direccion_query)


@router.get(
    "/debug/cuantitativo",
    response_model=DebugCuantitativoResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=True,
    summary="[DEV] Dump JSON cuantitativo sin IA",
    description=(
        "**Solo `settings.DEV_MODE=true`.** Ejecuta el motor cuantitativo y devuelve el JSON de métricas "
        "**sin FODA/LLM y sin PDF**. Requiere Bearer.\n\n"
        "Sirve para validar población, NSE, competencia, SVA, etc. antes de tratar el LLM "
        "como caja negra.\n\n"
        "No bypassa el entitlement del PDF pagado.\n\n"
        "Equivalente CLI: `scripts/debug_analisis_cuantitativo.py` (también puede generar Excel)."
    ),
)
def debug_cuantitativo(
    lat: float,
    lng: float,
    db: DbDep,
    user: UserDep,
    radio_metros: int = 1000,
    rubro: str = "cafeteria",
    tier: str = "premium",
):
    _ = user

    from app.core.config import settings

    if not settings.DEV_MODE:
        raise ValidationUserError("Este endpoint solo está disponible en modo desarrollo (settings.DEV_MODE=true).")

    from app.services.v0.analytics.analytics_service import procesar_calculo_analitico

    resultado = procesar_calculo_analitico(db=db, lat=lat, lng=lng, radio=radio_metros, rubro=rubro, tier=tier)

    return {"status": "debug", "nota": "Solo métricas cuantitativas, sin FODA ni PDF.", "metricas": resultado}
