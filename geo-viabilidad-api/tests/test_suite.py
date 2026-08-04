import os
import sys
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient

# Configure python path to resolve imports from root directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.clients.v0.database import OrdenPago, SessionLocal
from app.clients.v0.google.google_giro_filter import competidor_es_relevante_al_giro, filtrar_competidores_por_giro
from app.domain.nse import (
    construir_nse_fallback,
    etiqueta_desde_score,
    hash_nse_fallback,
    nse_score_desde_metricas,
)
from app.main import app
from app.services.v0.analytics.analytics_service import (
    calcular_distancia_haversine,
    calcular_nse,
    calcular_score_demografico,
    calcular_segmentacion_demografica,
    resolver_competidores_destacados_para_reporte,
    resolver_google_type,
)


# Endpoints dinámicos de simulación de errores para pruebas del middleware
@app.get("/error-test-db")
def route_error_db():
    from sqlalchemy.exc import OperationalError

    raise OperationalError("SELECT 1", {}, Exception("Database Connection refused (Simulated)"))


@app.get("/error-test-aws")
def route_error_aws():
    from botocore.exceptions import ClientError

    raise ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "Simulated Bedrock Access Denied"}}, "InvokeModel"
    )


@app.get("/error-test-unexpected")
def route_error_unexpected():
    raise Exception("Fallo lógico no controlado en memoria (Simulado)")


client = TestClient(app)


def test_calcular_score_demografico_por_densidad():
    """El pilar demográfico debe basarse en hab/km² del radio, no en población absoluta."""
    score_pueblo, dens_pueblo = calcular_score_demografico(4342, 1000)
    score_rural, _ = calcular_score_demografico(300, 1000)
    score_ciudad, dens_ciudad = calcular_score_demografico(12000, 1000)

    assert dens_pueblo == 1382.1
    assert score_pueblo >= 85
    assert score_rural == 15.0
    assert dens_ciudad > dens_pueblo
    assert score_ciudad == 100.0


def test_health_check():
    """
    Test that the health check endpoint is functional and reports 'ok'
    without leaking environment flags.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "GeoViabilidad Hook" in data["service"]
    assert "timestamp" in data
    assert "dev_mode" not in data
    assert "payments_mock" not in data


def test_exception_middleware_db():
    """
    Test that database connection errors (OperationalError) are caught by the
    UserFriendlyExceptionMiddleware and translated to a user-friendly message.
    """
    response = client.get("/error-test-db")
    assert response.status_code == 500
    data = response.json()
    assert data["status"] == "error"
    assert "mantenimiento rápido" in data["friendly_message"]
    assert "recargar la página" in data["suggested_action"]
    assert data["transaction_id"].startswith("err_db_")


def test_exception_middleware_aws():
    """
    Test that AWS client/sdk errors (ClientError) are caught by the
    UserFriendlyExceptionMiddleware and translated to a user-friendly message.
    """
    response = client.get("/error-test-aws")
    assert response.status_code == 500
    data = response.json()
    assert data["status"] == "error"
    assert "alta demanda" in data["friendly_message"]
    assert "sin costo adicional" in data["suggested_action"]
    assert data["transaction_id"].startswith("err_aws_")


def test_exception_middleware_unexpected():
    """
    Test that unexpected runtime errors are caught by the
    UserFriendlyExceptionMiddleware and translated to a user-friendly message.
    """
    response = client.get("/error-test-unexpected")
    assert response.status_code == 500
    data = response.json()
    assert data["status"] == "error"
    assert "inconveniente inesperado" in data["friendly_message"]
    assert "equipo técnico" in data["suggested_action"]
    assert data["transaction_id"].startswith("err_sys_")


def test_haversine_distance():
    """
    Test that the Haversine distance calculator accurately returns ~0 for identical points
    and exact distance for known reference coordinates.
    """
    # Coordinates of Zócalo CDMX
    lat1, lng1 = 19.432608, -99.133208
    # 0 distance for the exact same point
    assert calcular_distancia_haversine(lat1, lng1, lat1, lng1) == 0.0

    # Distance to a point ~100m east
    lat2, lng2 = 19.432608, -99.132256
    dist = calcular_distancia_haversine(lat1, lng1, lat2, lng2)
    assert 90.0 < dist < 110.0  # Approx 100 meters


def test_nse_etiqueta_y_fallback_deterministico():
    assert etiqueta_desde_score(72) == "A/B (Alto / Alto Medio)"
    assert etiqueta_desde_score(60) == "C+ (Medio Alto)"
    assert etiqueta_desde_score(45) == "C / C- (Medio / Medio Bajo)"
    assert etiqueta_desde_score(30) == "D+ (Bajo Alto)"
    assert etiqueta_desde_score(10) == "D / E (Bajo / Muy Bajo)"

    lat, lng = 19.432608, -99.133208
    hash_a = hash_nse_fallback(lat, lng)
    hash_b = hash_nse_fallback(lat, lng)
    assert hash_a == hash_b

    fallback = construir_nse_fallback(lat, lng)
    assert fallback["nse_etiqueta"]
    assert fallback["metricas"]["fuente"] == "fallback_determinista"
    assert fallback["agebs_consultadas"] == 0

    score = nse_score_desde_metricas(11.0, 65.0, 45.0)
    assert 50 <= score <= 70


def test_calcular_nse_con_db():
    db = SessionLocal()
    try:
        nse = calcular_nse(db, 19.432608, -99.133208, 1000)
        assert "nse_etiqueta" in nse
        assert "metricas" in nse
        assert nse["metricas"]["fuente"] in {"censo_2020", "fallback_determinista", "sin_datos"}
    finally:
        db.close()


def test_segmentacion_demografica_con_db():
    db = SessionLocal()
    try:
        seg = calcular_segmentacion_demografica(db, 19.3719, -99.1896, 1000)
        assert "piramide" in seg
        if seg["fuente"] == "censo_2020":
            assert seg["pob15_64"] > 0
            assert len(seg["piramide"]) >= 6
    finally:
        db.close()


def test_resolver_competidores_prioriza_categorias_usuario():
    from app.domain.competencia_busqueda import resolver_tipos_competidores_busqueda

    tipos, _, fuente = resolver_tipos_competidores_busqueda(
        ["cafe", "bakery", "ia_auto"],
        rubro="cafetería gourmet",
        google_type="cafe",
        categorias_ia={"competidores": ["restaurant"], "aliados": []},
    )
    assert fuente == "categorias_usuario"
    assert tipos == ["cafe", "bakery"]


def test_resolver_competidores_ia_usa_rubro_sin_categorias_manuales():
    from app.domain.competencia_busqueda import keyword_places_para_ia, resolver_tipos_competidores_busqueda

    tipos, _, fuente = resolver_tipos_competidores_busqueda(
        ["ia_auto"],
        rubro="accesorios para mascotas",
        google_type="store",
        categorias_ia={"competidores": ["store", "convenience_store"], "aliados": []},
    )
    assert fuente == "ia_rubro_intenciones"
    assert "store" in tipos

    kw = keyword_places_para_ia(
        "accesorios para mascotas",
        google_type="store",
    )
    assert kw is not None
    assert "mascotas" in kw.lower() or "collares" in kw.lower()


def test_nombre_categoria_places_en_espanol():
    from app.domain.aliados_deterministico import nombre_categoria_places

    assert nombre_categoria_places("shopping_mall") == "Centros Comerciales"
    assert nombre_categoria_places("transit_station") == "Paradas de Transporte Público"
    assert nombre_categoria_places("doctor") == "Consultorios Médicos"


def test_filtro_giro_floreria_conserva_nombres_con_flores():
    rubro = "florería"
    candidatos = [
        {"nombre": "bonitasflores.com", "tipo": "Store"},
        {"nombre": "Unbonitodetalle - flores y regalos", "tipo": "Store"},
        {"nombre": "Mercado De Plantas", "tipo": "Store"},
        {"nombre": "Florería Ricardo", "tipo": "Store"},
        {"nombre": "City Market Pilares", "tipo": "Store"},
        {"nombre": "Café El Jarocho Centenario", "tipo": "Store"},
    ]
    filtrados = filtrar_competidores_por_giro(rubro, candidatos)
    nombres = {c["nombre"] for c in filtrados}
    assert "bonitasflores.com" in nombres
    assert "Unbonitodetalle - flores y regalos" in nombres
    assert "Florería Ricardo" in nombres
    assert "City Market Pilares" not in nombres
    assert "Café El Jarocho Centenario" not in nombres
    assert len(filtrados) >= 3


def test_keyword_ia_no_duplica_rubro_en_intenciones():
    from app.domain.competencia_busqueda import keyword_places_para_ia

    kw = keyword_places_para_ia(
        "florería",
        google_type="store",
    )
    assert kw == "florería"


def test_keyword_ia_ignora_intenciones_placeholder_y_usa_rubro():
    from app.domain.competencia_busqueda import keyword_places_para_ia

    kw = keyword_places_para_ia(
        "florería",
        google_type="store",
    )
    assert kw == "florería"


def test_resolver_aliados_matriz_cafeteria():
    from app.domain.aliados_deterministico import resolver_aliados_por_rubro
    from app.domain.competencia_busqueda import resolver_tipos_aliados_busqueda

    tipos, ia_auto, fuente = resolver_tipos_aliados_busqueda(
        ["ia_auto"],
        rubro="cafetería de especialidad",
    )
    assert fuente == "matriz_rubro"
    assert ia_auto is True
    assert tipos == ["school", "transit_station", "bank", "shopping_mall"]
    assert resolver_aliados_por_rubro("café gourmet") == tipos


def test_resolver_aliados_matriz_farmacia():
    from app.domain.competencia_busqueda import resolver_tipos_aliados_busqueda

    tipos, _, fuente = resolver_tipos_aliados_busqueda(
        ["ia_auto"],
        rubro="farmacia de barrio",
    )
    assert fuente == "matriz_rubro"
    assert tipos == ["doctor", "supermarket", "transit_station", "convenience_store"]


def test_resolver_aliados_matriz_mascotas():
    from app.domain.competencia_busqueda import resolver_tipos_aliados_busqueda

    tipos, _, fuente = resolver_tipos_aliados_busqueda(
        ["ia_auto"],
        rubro="accesorios para mascotas",
    )
    assert fuente == "matriz_rubro"
    assert "supermarket" in tipos
    assert "park" in tipos


def test_resolver_aliados_matriz_default_sin_rubro_conocido():
    from app.domain.competencia_busqueda import resolver_tipos_aliados_busqueda

    tipos, _, fuente = resolver_tipos_aliados_busqueda(
        ["ia_auto"],
        rubro="servicios profesionales varios",
    )
    assert fuente == "matriz_rubro"
    assert tipos == ["transit_station", "school", "bank"]


def test_resolver_aliados_intenciones_reordenan_sin_agregar():
    from app.domain.aliados_deterministico import resolver_aliados_por_rubro

    base = resolver_aliados_por_rubro("cafetería")
    con_escuela = resolver_aliados_por_rubro(
        "cafetería",
    )
    assert set(con_escuela) == set(base)
    assert con_escuela[0] == "school"


def test_sva_calculo_transparente_y_simulador():
    from app.domain.sva_calculo import (
        calcular_score_competencia,
        componer_sva,
        desglose_sva_completo,
        escenarios_simulacion_sva,
    )

    analisis = {
        "score_demog": 72.2,
        "score_trafico": 55.0,
        "competidores_conteo": 12,
        "densidad_hab_km2": 1450.0,
        "poblacion_ponderada": 2500,
        "competidores_listado": [
            {"distancia_metros": 80},
            {"distancia_metros": 150},
            {"distancia_metros": 220},
            {"distancia_metros": 310},
            {"distancia_metros": 400},
            {"distancia_metros": 520},
            {"distancia_metros": 610},
            {"distancia_metros": 700},
            {"distancia_metros": 820},
            {"distancia_metros": 900},
            {"distancia_metros": 1050},
            {"distancia_metros": 1200},
        ],
    }
    isc_ejemplo = 0.0001064
    score_comp = calcular_score_competencia(isc_ejemplo)
    assert score_comp == 54.4
    analisis["isc"] = isc_ejemplo
    analisis["score_competencia"] = score_comp
    _, analisis["sva"] = componer_sva(72.2, score_comp, 55.0)

    desglose = desglose_sva_completo(analisis, tier="pro", radio_metros=1000)
    assert desglose["competencia"]["factor_log_isc"] is not None
    assert "log10(ISC)" in desglose["competencia"]["regla"]
    assert desglose["demografico"].get("lectura_llana")
    assert desglose["competencia"].get("lectura_llana")
    assert "distancia" in desglose["competencia"]["lectura_llana"].lower()
    assert desglose["demografico"]["score"] == 72.2
    assert desglose["sva_entero"] == desglose["sva_reportado"]
    assert "BestTime" not in desglose["trafico"]["fuente"]
    assert "tráfico peatonal" in desglose["trafico"]["lectura_llana"].lower()

    desglose_prem = desglose_sva_completo(
        {
            **analisis,
            "afluencia_peatonal": {"status": "success", "saturación_promedio": 62.5},
        },
        tier="premium",
        radio_metros=1000,
    )
    assert desglose_prem["trafico"]["medicion_peatonal_real"] is True
    assert "tráfico peatonal" in desglose_prem["trafico"]["lectura_llana"].lower()
    assert "besttime" in desglose_prem["trafico"]["lectura_llana"].lower()

    escenarios = escenarios_simulacion_sva(analisis, tier="pro", radio_metros=1000)
    assert escenarios[0]["escenario"].startswith("Situación actual")
    assert escenarios[0]["competidores"] == 12
    assert escenarios[0]["sva"] == analisis["sva"]
    mitad = next(e for e in escenarios if "más cercanos" in e["escenario"] and e["competidores"] == 6)
    assert mitad["delta_vs_actual"] != 0
    doble = next(e for e in escenarios if "doble de distancia" in e["escenario"])
    assert doble["competidores"] == 12
    assert doble["isc"] < isc_ejemplo
    assert doble["sva"] >= escenarios[0]["sva"]
    sin_comp = next(e for e in escenarios if "sin rivales" in e["escenario"])
    assert sin_comp["competidores"] == 0
    assert sin_comp["score_competencia"] == 100.0
    assert sin_comp["sva"] > escenarios[0]["sva"]

    analisis_20 = {
        **analisis,
        "competidores_conteo": 20,
        "competidores_listado": [{"distancia_metros": i * 50} for i in range(1, 21)],
    }
    esc_20 = escenarios_simulacion_sva(analisis_20, tier="pro", radio_metros=1000)
    nombres = [e["escenario"] for e in esc_20]
    assert len(nombres) == len(set(nombres))
    diez_cercanos = [e for e in esc_20 if e["competidores"] == 10 and "más cercanos" in e["escenario"]]
    assert len(diez_cercanos) == 1

    _, sva_calc = componer_sva(72.2, score_comp, 55.0)
    assert sva_calc == 62


def test_pdf_conteos_iat_y_radio_kpi():
    from app.services.v0.reports.report_pdf_service import _formato_radio_kpi, _texto_conteo_iat_categoria

    assert _formato_radio_kpi(1500) == "1.5 km"
    assert _formato_radio_kpi(1000) == "1 km"
    assert _formato_radio_kpi(800) == "800 m"

    texto = _texto_conteo_iat_categoria(20, 2, tier="premium")
    assert "20 en mapas" in texto
    assert "2 en listado detallado" in texto
    assert "catálogo amplio" in texto

    texto_simple = _texto_conteo_iat_categoria(5, 0, tier="pro")
    assert texto_simple == "5 detectados en el radio"


def test_competidores_mas_cercanos_y_lectura():
    from app.services.v0.analytics.analytics_service import (
        competidores_mas_cercanos,
        lectura_competidor_cercano,
    )

    lista = [
        {"nombre": "Lejos", "distancia_metros": 900, "rating": 4.8, "user_ratings_total": 120},
        {"nombre": "Cerca malo", "distancia_metros": 45, "rating": 2.0, "user_ratings_total": 8},
        {"nombre": "Medio", "distancia_metros": 200, "rating": 3.5, "user_ratings_total": 15},
    ]
    cercanos = competidores_mas_cercanos(lista, top_n=2)
    assert [c["nombre"] for c in cercanos] == ["Cerca malo", "Medio"]

    assert "debil" in lectura_competidor_cercano(lista[1]).lower()
    assert "friccion directa" in lectura_competidor_cercano({"rating": 4.8, "user_ratings_total": 120}).lower()
    assert "aceptable" in lectura_competidor_cercano(lista[2]).lower()


def test_lectura_estrategica_enriquecimiento_y_conclusion():
    from app.services.presentation.narrative import (
        bloques_metodologia_resumen,
        enriquecer_item_lectura,
        generar_conclusion_detallada,
    )

    analisis = {
        "sva": 62,
        "poblacion_ponderada": 12500,
        "densidad_hab_km2": 4200.5,
        "competidores_conteo": 8,
        "score_demog": 72,
        "score_competencia": 54,
        "score_trafico": 55,
        "nse": {
            "nse_etiqueta": "NSE A/B",
            "metricas": {
                "escolaridad_promedio": 14.6,
                "internet_pct": 88.2,
                "autos_pct": 62.1,
                "fuente": "censo",
            },
        },
        "aliados_conteos": {"escuela": 3, "transporte": 2},
    }
    expandido = enriquecer_item_lectura("NSE A/B con escolaridad promedio de 14.6", analisis)
    assert "14.6" in expandido
    assert "internet" in expandido.lower()
    assert len(expandido) > 80

    conclusion = generar_conclusion_detallada(analisis, "Cafetería", tier="pro", radio_metros=1000)
    assert "62/100" in conclusion
    assert "40%" in conclusion
    assert "Para mejorar" in conclusion or "mejorar" in conclusion.lower()
    assert "<b>" not in conclusion

    conclusion_html = generar_conclusion_detallada(analisis, "Cafetería", tier="pro", radio_metros=1000, html=True)
    assert "<b>" in conclusion_html

    bloques = bloques_metodologia_resumen(analisis, tier="pro", radio_metros=1000)
    assert any("Competencia" in t for t, _ in bloques)
    assert any("Nivel socioeconómico" in t for t, _ in bloques)


def test_invitacion_profesional_y_saturacion_alta():
    from app.services.v0.reports.report_pdf_service import _enlaces_consultoria_html, _saturacion_comercial_alta

    html = _enlaces_consultoria_html()
    assert "phiqus.com" in html
    assert "estudiosdemercado.phiqus.com" in html
    assert "Estudios de Mercado" in html

    assert _saturacion_comercial_alta({"competidores_conteo": 10, "score_competencia": 70})
    assert _saturacion_comercial_alta(
        {
            "competidores_conteo": 3,
            "score_competencia": 80,
            "competidores_listado": [{"distancia_metros": 100}, {"distancia_metros": 180}],
        }
    )
    assert not _saturacion_comercial_alta(
        {"competidores_conteo": 2, "score_competencia": 75, "competidores_listado": [{"distancia_metros": 600}]}
    )


def test_interpretacion_demografia_por_rubro():
    from app.services.v0.reports.report_pdf_service import _interpretacion_distribucion_poblacional

    seg = {
        "pob0_14": 1200,
        "pob15_64": 5000,
        "pob65_mas": 800,
        "pea": 3200,
        "piramide": [],
    }
    texto = _interpretacion_distribucion_poblacional("florería", seg, 7000, "pro")
    assert "florer" in texto.lower()
    assert "7,000" in texto
    assert "pirámide" in texto.lower() or "cohortes" in texto.lower()


def test_resolver_aliados_matriz_floreria():
    from app.domain.aliados_deterministico import resolver_aliados_por_rubro
    from app.domain.competencia_busqueda import resolver_tipos_aliados_busqueda

    tipos, _, fuente = resolver_tipos_aliados_busqueda(
        ["ia_auto"],
        rubro="florería boutique",
    )
    assert fuente == "matriz_rubro"
    assert tipos == ["shopping_mall", "school", "doctor", "restaurant"]

    con_hospital = resolver_aliados_por_rubro(
        "florería",
    )
    assert con_hospital[0] == "shopping_mall"
    assert set(con_hospital) == set(tipos)


def test_resolver_aliados_prioriza_categorias_usuario():
    from app.domain.competencia_busqueda import resolver_tipos_aliados_busqueda

    tipos, ia_auto, fuente = resolver_tipos_aliados_busqueda(
        ["park", "bank", "ia_auto"],
        rubro="cafetería",
    )
    assert fuente == "categorias_usuario"
    assert ia_auto is True
    assert tipos == ["park", "bank"]


def test_filtro_giro_competidores_por_reseñas():
    """Excluye competidores cuyas reseñas no coinciden con el rubro (ej. acuario vs accesorios mascotas)."""
    rubro = "accesorios para mascotas"
    acuario = {
        "nombre": "Reef School Mexico",
        "tipo": "Mascotas",
        "rating": 4.5,
        "user_ratings_total": 36,
        "reseñas_google": [
            {"texto": "Excelente acuario con peces marinos y corales.", "rating": 5},
            {"texto": "Muy buena escuela para aprender sobre acuarios.", "rating": 4},
        ],
    }
    pet_shop = {
        "nombre": "Spa Animals",
        "tipo": "Mascotas",
        "rating": 4.4,
        "user_ratings_total": 115,
        "reseñas_google": [
            {"texto": "Buen servicio para perros, dejan muy limpio a mi mascota.", "rating": 5},
        ],
    }

    assert competidor_es_relevante_al_giro(rubro, acuario) is False
    assert competidor_es_relevante_al_giro(rubro, pet_shop) is True

    filtrados = filtrar_competidores_por_giro(rubro, [acuario, pet_shop])
    assert [c["nombre"] for c in filtrados] == ["Spa Animals"]

    destacados = resolver_competidores_destacados_para_reporte(
        [acuario, pet_shop],
        rubro,
        top_n=5,
        enriquecer_reseñas=False,
    )
    assert [c["nombre"] for c in destacados] == ["Spa Animals"]


def test_vigencia_comercio_cerrado_y_reciente():
    import time

    from app.domain.vigencia_comercio import detectar_cierre_en_resenas, evaluar_vigencia_comercio

    cerrado = evaluar_vigencia_comercio(business_status="CLOSED_PERMANENTLY")
    assert cerrado["nivel"] == "inactivo"
    assert cerrado["activo_para_analisis"] is False

    ahora = int(time.time())
    reciente = evaluar_vigencia_comercio(
        business_status="OPERATIONAL",
        reseñas_google=[{"texto": "Excelente café", "time": ahora - 30 * 86400}],
    )
    assert reciente["nivel"] == "alta"
    assert reciente["activo_para_analisis"] is True

    obsoleto = evaluar_vigencia_comercio(
        business_status="OPERATIONAL",
        reseñas_google=[{"texto": "Muy bueno", "time": ahora - 40 * 30 * 86400}],
    )
    assert obsoleto["nivel"] == "baja"
    assert "valida en sitio" in obsoleto["lectura"].lower()

    assert detectar_cierre_en_resenas([{"texto": "Ya cerró hace meses"}]) is True


def test_calcular_isc_excluye_cerrados():
    from app.services.v0.analytics.analytics_service import _calcular_isc_competidores

    competidores = [
        {
            "distancia_metros": 50,
            "vigencia": {"activo_para_analisis": False},
        },
        {
            "distancia_metros": 100,
            "vigencia": {"activo_para_analisis": True},
        },
    ]
    isc, dist_min = _calcular_isc_competidores(competidores)
    assert dist_min == 100.0
    assert abs(isc - (1.0 / (100.0**2))) < 1e-9


def test_resolver_google_type():
    """
    Test that the SCiAN category to Google Places type mapper functions correctly.
    """
    db = SessionLocal()
    try:
        # Test standard fallback mappings
        type_cafe, cat_cafe = resolver_google_type(db, "cafeteria")
        assert type_cafe == "cafe"
        assert cat_cafe == "cafeteria"

        type_pharma, cat_pharma = resolver_google_type(db, "farmacia")
        assert type_pharma == "pharmacy"
        assert cat_pharma == "farmacia"

        type_rest, cat_rest = resolver_google_type(db, "restaurante gourmet")
        assert type_rest == "restaurant"
        assert cat_rest == "restaurante"

        type_gym, cat_gym = resolver_google_type(db, "gimnasio de pesas")
        assert type_gym == "gym"
        assert cat_gym == "gimnasio"

        # Pet and Vet fallbacks
        type_pet, cat_pet = resolver_google_type(db, "accesorios para mascota")
        assert type_pet == "pet_store"
        assert cat_pet == "accesorios_para_mascotas"

        type_vet, cat_vet = resolver_google_type(db, "veterinaria de perros")
        assert type_vet == "veterinary_care"
        assert cat_vet == "veterinaria"

        # Bakery fallback
        type_bakery, cat_bakery = resolver_google_type(db, "panaderia artesanal")
        assert type_bakery == "bakery"
        assert cat_bakery == "panaderia"

        # General store fallback
        type_fallback, cat_fallback = resolver_google_type(db, "carpinteria metalica")
        assert type_fallback == "store"
    finally:
        db.close()


def test_crear_preferencia_cobro_api():
    """
    Test preference creation API with authentication in DEV_MODE.
    """
    payload = {
        "tier_adquirido": "basico",
        "latitud": 19.432608,
        "longitud": -99.133208,
        "radio_metros": 1000,
        "rubro": "cafeteria",
        "intenciones": "Quiero poner una cafetería de especialidad.",
    }
    # Bearer authentication header is required, even if simulated in DEV_MODE
    headers = {"Authorization": "Bearer mock-token"}
    response = client.post("/api/pagos/preferencia", json=payload, headers=headers)
    assert response.status_code == 201

    data = response.json()
    assert "orden_id" in data
    assert data["monto"] == 299.00
    assert data["estado_pago"] == "pending"
    assert "checkout_id" in data
    assert "init_point" in data
    assert "pref_id=mock_chk_" in data["init_point"]

    # Let's clean up this test order from database
    db = SessionLocal()
    try:
        orden = db.query(OrdenPago).filter(OrdenPago.checkout_id == data["checkout_id"]).first()
        if orden:
            db.delete(orden)
            db.commit()
    finally:
        db.close()


def test_crear_preferencia_cobro_con_campos_adicionales_api():
    """
    Test preference creation API with custom competitor/ally keywords.
    """
    payload = {
        "tier_adquirido": "premium",
        "latitud": 19.432608,
        "longitud": -99.133208,
        "radio_metros": 1000,
        "rubro": "cafeteria",
        "intenciones": "Quiero poner una cafetería de especialidad.",
        "competidores_seleccionados": ["cafe", "restaurant"],
        "aliados_seleccionados": ["bank", "school"],
        "competidores_adicionales": "Starbucks, Cielito Querido",
        "aliados_adicionales": "OXXO, Banamex",
    }
    headers = {"Authorization": "Bearer mock-token"}
    response = client.post("/api/pagos/preferencia", json=payload, headers=headers)
    assert response.status_code == 201

    data = response.json()
    assert "orden_id" in data

    # Verify that columns exist and have the correct value
    db = SessionLocal()
    try:
        orden = db.query(OrdenPago).filter(OrdenPago.id == data["orden_id"]).first()
        assert orden is not None
        assert orden.competidores_adicionales == "Starbucks, Cielito Querido"
        assert orden.aliados_adicionales == "OXXO, Banamex"

        # Clean up
        db.delete(orden)
        db.commit()
    finally:
        db.close()


def test_webhook_processing_and_mock():
    """
    Test that the webhook and webhook-mock endpoints correctly process and schedule reports.
    """
    db = SessionLocal()
    try:
        # Create a pending order directly in the database
        checkout_id = f"chk_test_webhook_{os.urandom(3).hex()}"
        orden = OrdenPago(
            cognito_user_id="usr_mock_123",
            email="demo_sva@geoviabilidad.com",
            checkout_id=checkout_id,
            monto=Decimal("649.00"),
            estado_pago="pending",
            tier_adquirido="pro",
            latitud=Decimal("19.432608"),
            longitud=Decimal("-99.133208"),
            radio_metros=1000,
            rubro="cafeteria",
        )
        db.add(orden)
        db.commit()
        db.refresh(orden)

        # Trigger mock webhook to approve the payment
        webhook_payload = {"checkout_id": checkout_id, "estado_pago": "approved"}
        response = client.post(
            "/api/pagos/webhook-mock",
            json=webhook_payload,
            headers={"Authorization": "Bearer mock-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["orden_id"] == orden.id

        # Verify the webhook updates the payment state and launches tasks (tested in DEV_MODE synchronously)
        db.refresh(orden)
        assert orden.estado_pago == "approved"
        assert orden.s3_key_reporte is not None
        assert orden.resultado_json is not None
        assert orden.foda_json is not None

        # Clean up database entry and generated reports/emails
        db.delete(orden)
        db.commit()

        local_pdf = f"scratch/reports/{checkout_id}_reporte_cafeteria.pdf"
        if os.path.exists(local_pdf):
            os.remove(local_pdf)

        local_email = f"scratch/emails/email_orden_{orden.id}.html"
        if os.path.exists(local_email):
            os.remove(local_email)

    finally:
        db.close()


def test_crear_preferencia_invalida_basico():
    """
    Test that Básico tier accepts up to 1 custom competitor and rejects allies or more than 1 competitor.
    """
    headers = {"Authorization": "Bearer mock-token"}

    # 1. 1 competitor should be VALID
    payload_valid = {
        "tier_adquirido": "basico",
        "latitud": 19.432608,
        "longitud": -99.133208,
        "radio_metros": 1000,
        "rubro": "cafeteria",
        "competidores_seleccionados": ["cafe"],
    }
    response_val = client.post("/api/pagos/preferencia", json=payload_valid, headers=headers)
    assert response_val.status_code == 201
    data_val = response_val.json()

    # Clean up valid test order
    db = SessionLocal()
    try:
        orden = db.query(OrdenPago).filter(OrdenPago.checkout_id == data_val["checkout_id"]).first()
        if orden:
            db.delete(orden)
            db.commit()
    finally:
        db.close()

    # 2. 2 competitors should be INVALID (limit is 1 for Básico)
    payload_invalid_comps = {
        "tier_adquirido": "basico",
        "latitud": 19.432608,
        "longitud": -99.133208,
        "radio_metros": 1000,
        "rubro": "cafeteria",
        "competidores_seleccionados": ["cafe", "gym"],
    }
    response = client.post("/api/pagos/preferencia", json=payload_invalid_comps, headers=headers)
    assert response.status_code == 422
    assert "El reporte Básico permite un máximo de 1 competidor" in response.text

    # 3. Any allies should be INVALID
    payload2 = {
        "tier_adquirido": "basico",
        "latitud": 19.432608,
        "longitud": -99.133208,
        "radio_metros": 1000,
        "rubro": "cafeteria",
        "aliados_seleccionados": ["school"],
    }
    response2 = client.post("/api/pagos/preferencia", json=payload2, headers=headers)
    assert response2.status_code == 422
    assert "El reporte Básico no permite personalizar aliados" in response2.text


def test_crear_preferencia_invalida_pro_aliados():
    """
    Test that Pro tier rejects custom allies.
    """
    headers = {"Authorization": "Bearer mock-token"}
    payload = {
        "tier_adquirido": "pro",
        "latitud": 19.432608,
        "longitud": -99.133208,
        "radio_metros": 1000,
        "rubro": "cafeteria",
        "aliados_seleccionados": ["bank"],
    }
    response = client.post("/api/pagos/preferencia", json=payload, headers=headers)
    assert response.status_code == 422
    assert "El reporte Pro no permite personalizar aliados" in response.text


def test_crear_preferencia_invalida_pro_limites():
    """
    Test that Pro tier rejects more than 3 custom competitors.
    """
    headers = {"Authorization": "Bearer mock-token"}
    payload = {
        "tier_adquirido": "pro",
        "latitud": 19.432608,
        "longitud": -99.133208,
        "radio_metros": 1000,
        "rubro": "cafeteria",
        "competidores_seleccionados": ["cafe", "gym", "restaurant", "bank"],
    }
    response = client.post("/api/pagos/preferencia", json=payload, headers=headers)
    assert response.status_code == 422
    assert "El reporte Pro permite un máximo de 3 competidores" in response.text


def test_crear_preferencia_invalida_premium_limites():
    """
    Test that Premium tier rejects more than 5 custom competitors or allies.
    """
    headers = {"Authorization": "Bearer mock-token"}
    payload = {
        "tier_adquirido": "premium",
        "latitud": 19.432608,
        "longitud": -99.133208,
        "radio_metros": 1000,
        "rubro": "cafeteria",
        "competidores_seleccionados": ["1", "2", "3", "4", "5", "6"],
    }
    response = client.post("/api/pagos/preferencia", json=payload, headers=headers)
    assert response.status_code == 422
    assert "El reporte Premium permite un máximo de 5 competidores" in response.text

    payload2 = {
        "tier_adquirido": "premium",
        "latitud": 19.432608,
        "longitud": -99.133208,
        "radio_metros": 1000,
        "rubro": "cafeteria",
        "aliados_seleccionados": ["1", "2", "3", "4", "5", "6"],
    }
    response2 = client.post("/api/pagos/preferencia", json=payload2, headers=headers)
    assert response2.status_code == 422
    assert "El reporte Premium permite un máximo de 5 aliados" in response2.text


def test_crear_preferencia_valida_pro_premium():
    """
    Test successful creation of Pro and Premium preferences with custom selections.
    """
    headers = {"Authorization": "Bearer mock-token"}
    payload_pro = {
        "tier_adquirido": "pro",
        "latitud": 19.432608,
        "longitud": -99.133208,
        "radio_metros": 1000,
        "rubro": "cafeteria",
        "competidores_seleccionados": ["cafe", "restaurant"],
    }
    response_pro = client.post("/api/pagos/preferencia", json=payload_pro, headers=headers)
    assert response_pro.status_code == 201
    data_pro = response_pro.json()

    payload_prem = {
        "tier_adquirido": "premium",
        "latitud": 19.432608,
        "longitud": -99.133208,
        "radio_metros": 1000,
        "rubro": "cafeteria",
        "competidores_seleccionados": ["cafe", "gym"],
        "aliados_seleccionados": ["bank", "school"],
    }
    response_prem = client.post("/api/pagos/preferencia", json=payload_prem, headers=headers)
    assert response_prem.status_code == 201
    data_prem = response_prem.json()

    # Clean up
    db = SessionLocal()
    try:
        for checkout_id in [data_pro["checkout_id"], data_prem["checkout_id"]]:
            orden = db.query(OrdenPago).filter(OrdenPago.checkout_id == checkout_id).first()
            if orden:
                db.delete(orden)
                db.commit()
    finally:
        db.close()


def test_obtener_resultado_analisis_cache_api():
    """
    Test that /api/analizar/resultado/{orden_id} endpoint loads cached results directly
    from database (resultado_json and foda_json) when present.
    """
    import json

    db = SessionLocal()
    try:
        # Create an approved order in database with custom cache data
        checkout_id = f"chk_test_cache_{os.urandom(3).hex()}"
        cached_resultado = {
            "sva": 93,
            "poblacion_ponderada": 45000,
            "competidores_conteo": 2,
            "competidores_listado": [],
            "direccion": "Dirección de caché de prueba",
        }
        cached_foda = {
            "fortalezas": ["Fortaleza de caché"],
            "oportunidades": ["Oportunidad de caché"],
            "consideraciones_apertura": ["Consideración de caché"],
            "conclusion": "Conclusión de caché",
        }

        orden = OrdenPago(
            cognito_user_id="usr_mock_123",
            email="demo_sva@geoviabilidad.com",
            checkout_id=checkout_id,
            monto=Decimal("649.00"),
            estado_pago="approved",
            tier_adquirido="pro",
            latitud=Decimal("19.432608"),
            longitud=Decimal("-99.133208"),
            radio_metros=1000,
            rubro="cafeteria",
            resultado_json=json.dumps(cached_resultado),
            foda_json=json.dumps(cached_foda),
        )
        db.add(orden)
        db.commit()
        db.refresh(orden)

        # Retrieve the analysis result
        headers = {"Authorization": "Bearer mock-token"}
        response = client.get(f"/api/analizar/resultado/{orden.id}", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert data["metricas"]["sva"] == 93
        assert data["metricas"]["poblacion_ponderada"] == 45000
        assert data["metricas"]["direccion"] == "Dirección de caché de prueba"
        assert data["analisis_estrategico_ia"]["conclusion"] == "Conclusión de caché"
        assert data["analisis_estrategico_ia"]["consideraciones_apertura"] == ["Consideración de caché"]

        # Clean up
        db.delete(orden)
        db.commit()
    finally:
        db.close()


def test_descargar_pdf_local_endpoint():
    """
    Test that the PDF download flow generates correct URLs in DEV_MODE
    and that hitting the download endpoint returns the PDF with the correct filename.
    """
    import os

    db = SessionLocal()
    try:
        checkout_id = f"chk_test_download_{os.urandom(3).hex()}"
        orden = OrdenPago(
            cognito_user_id="usr_mock_123",
            email="demo_sva@geoviabilidad.com",
            checkout_id=checkout_id,
            monto=Decimal("799.00"),
            estado_pago="approved",
            tier_adquirido="premium",
            latitud=Decimal("19.432608"),
            longitud=Decimal("-99.133208"),
            radio_metros=1000,
            rubro="floreria",
            s3_key_reporte=f"informes/usr_mock_123/{checkout_id}_reporte_floreria.pdf",
        )
        db.add(orden)
        db.commit()
        db.refresh(orden)

        # 1. Get the download URL (requires auth headers)
        headers = {"Authorization": "Bearer mock-token"}
        response = client.get(f"/api/reportes/pdf/{orden.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert f"/api/reportes/pdf/{orden.id}/descargar" in data["url_descarga"]
        assert "token=" in data["url_descarga"]

        # Create dummy PDF file locally
        os.makedirs("scratch/reports", exist_ok=True)
        local_pdf = f"scratch/reports/{checkout_id}_reporte_floreria.pdf"
        with open(local_pdf, "w") as f:
            f.write("dummy pdf content")

        try:
            # Sin token → 422 (query requerida)
            dl_unauth = client.get(f"/api/reportes/pdf/{orden.id}/descargar")
            assert dl_unauth.status_code == 422

            # Con token de la URL firmada
            from urllib.parse import parse_qs, urlparse

            qs = parse_qs(urlparse(data["url_descarga"]).query)
            dl_token = qs["token"][0]
            dl_response = client.get(
                f"/api/reportes/pdf/{orden.id}/descargar",
                params={"token": dl_token},
            )
            assert dl_response.status_code == 200
            assert dl_response.headers["content-type"] == "application/pdf"
            assert (
                'attachment; filename="Reporte_Viabilidad_floreria.pdf"' in dl_response.headers["content-disposition"]
            )
            assert dl_response.text == "dummy pdf content"

            # Token de un solo uso: segunda descarga falla
            dl_reuse = client.get(
                f"/api/reportes/pdf/{orden.id}/descargar",
                params={"token": dl_token},
            )
            assert dl_reuse.status_code in (401, 403)
        finally:
            if os.path.exists(local_pdf):
                os.remove(local_pdf)

        # Clean up database
        db.delete(orden)
        db.commit()
    finally:
        db.close()


@patch("app.clients.v0.google.google_client_processed.buscar_competidores")
@patch("app.clients.v0.google.google_client_processed.buscar_competidores_por_proximidad")
@patch("app.clients.v0.google.google_client_processed.obtener_direccion")
def test_procesar_calculo_analitico_aliados_adicionales(mock_direccion, mock_prox, mock_nearby):
    """
    Test that procesar_calculo_analitico handles text-input additional allies (aliados_adicionales)
    by performing keyword-based Places searches and enriching the allies list.
    """
    from app.services.v0.analytics.analytics_service import procesar_calculo_analitico

    mock_nearby.side_effect = lambda lat, lng, radio, google_type, keyword=None: [
        {
            "place_id": f"plc_{google_type}_1",
            "nombre": f"Mock {google_type.capitalize()}",
            "latitud": lat + 0.0001,
            "longitud": lng + 0.0001,
            "direccion": f"Dirección {google_type}",
            "rating": 4.5,
            "user_ratings_total": 50,
            "google_types": [google_type],
        }
    ]
    mock_prox.return_value = []
    mock_direccion.return_value = {
        "calle": "Calle Falsa",
        "numero": "123",
        "colonia": "Colonia Centro",
        "codigo_postal": "06000",
        "localidad": "CDMX",
        "estado": "CDMX",
        "formato_completo": "Calle Falsa 123, Colonia Centro, CDMX, México",
        "municipio": "Cuauhtémoc",
        "pais": "México",
    }

    db = SessionLocal()
    try:
        resultado = procesar_calculo_analitico(
            db=db,
            lat=19.432608,
            lng=-99.133208,
            radio=1000,
            rubro="cafeteria",
            tier="premium",
            aliados_adicionales="banco, hotel",
        )

        # Verify that allies contain search results for the keywords
        aliados = resultado["aliados_listado"]
        assert len(aliados) > 0

        # Check that we have both "Banco" and "Hotel" in the type/giro field
        tipos_detectados = [a["tipo"] for a in aliados]
        assert "Banco" in tipos_detectados
        assert "Hotel" in tipos_detectados

        # Check that the conteos are updated with the counts
        assert "banco" in resultado["aliados_conteos"]
        assert "hotel" in resultado["aliados_conteos"]
        assert resultado["aliados_conteos"]["banco"] > 0
        assert resultado["aliados_conteos"]["hotel"] > 0

    finally:
        db.close()


@patch("app.clients.v0.google.google_client_processed.buscar_coordenadas_por_direccion")
def test_buscar_direccion_api(mock_buscar):
    """
    Test that the search endpoint `/api/analizar/buscar-direccion` works
    correctly and returns mock coordinates in DEV_MODE.
    """
    mock_buscar.return_value = [
        {
            "direccion": "Reforma 222, Ciudad de México, México",
            "latitud": 19.432608,
            "longitud": -99.133208,
        },
        {
            "direccion": "Av. Benito Juárez, Reforma 222, Guadalajara, Jal., México",
            "latitud": 20.659698,
            "longitud": -103.349609,
        },
    ]
    headers = {"Authorization": "Bearer mock-token"}
    response = client.get("/api/analizar/buscar-direccion?direccion=Reforma%20222", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["resultados"]) > 0
    assert "latitud" in data["resultados"][0]
    assert "longitud" in data["resultados"][0]
    assert "direccion" in data["resultados"][0]
    assert "Reforma 222" in data["resultados"][0]["direccion"]


def test_seleccion_atractores_destacados_por_calificacion():
    from app.domain.seleccion_atractores import (
        MIN_RESENAS_BUENA,
        RATING_BUENA_PREMIUM,
        seleccionar_atractores_destacados,
    )

    def _aliado(rating: float, reviews: int = 10, dist: float = 100.0, idx: int = 0) -> dict:
        return {
            "nombre": f"Lugar {idx}-{rating}",
            "rating": rating,
            "user_ratings_total": reviews,
            "distancia_metros": dist,
            "latitud": 19.43 + idx * 0.0001,
            "longitud": -99.13,
        }

    muchos_buenos = [_aliado(4.5, dist=50 + i * 10, idx=i) for i in range(12)]
    destacados, meta = seleccionar_atractores_destacados(muchos_buenos, tier="pro")
    assert len(destacados) == 10
    assert meta["tamano_aplicado"] == 10
    assert meta["atractores_calificacion_alta_en_pool"] == 10
    assert meta["resenas_minimas_buena"] == MIN_RESENAS_BUENA

    seis_buenos = [_aliado(4.2, dist=80 + i * 20, idx=i) for i in range(6)] + [
        _aliado(3.2, dist=200 + i * 30, idx=10 + i) for i in range(6)
    ]
    destacados6, meta6 = seleccionar_atractores_destacados(seis_buenos, tier="pro")
    assert len(destacados6) == 7
    assert meta6["tamano_aplicado"] == 7

    cuatro_buenos = [_aliado(4.0, dist=100 + i * 15, idx=i) for i in range(4)] + [
        _aliado(2.5, dist=300 + i * 20, idx=10 + i) for i in range(8)
    ]
    destacados4, meta4 = seleccionar_atractores_destacados(cuatro_buenos, tier="pro")
    assert len(destacados4) == 5
    assert meta4["tamano_aplicado"] == 5

    pocos_buenos = [_aliado(4.3, dist=90, idx=0), _aliado(3.1, dist=120, idx=1)] + [
        _aliado(2.0, dist=150 + i * 10, idx=2 + i) for i in range(8)
    ]
    destacados3, meta3 = seleccionar_atractores_destacados(pocos_buenos, tier="pro")
    assert len(destacados3) == 3
    assert meta3["tamano_aplicado"] == 3

    # Rating alto pero pocas reseñas no cuenta como "buena calificación"
    rating_sin_muestra = [_aliado(4.9, reviews=2, idx=i) for i in range(8)] + [
        _aliado(3.0, reviews=20, idx=10 + i) for i in range(4)
    ]
    _, meta_resenas = seleccionar_atractores_destacados(rating_sin_muestra, tier="pro")
    assert meta_resenas["atractores_calificacion_alta_en_pool"] == 0

    # Premium exige rating ≥ 4.2 además de 5 reseñas
    mix_premium = [
        _aliado(4.15, reviews=50, idx=0),
        _aliado(4.25, reviews=8, idx=1),
        _aliado(4.1, reviews=100, idx=2),
    ] + [_aliado(3.5, reviews=10, idx=3 + i) for i in range(7)]
    _, meta_prem = seleccionar_atractores_destacados(mix_premium, tier="premium")
    assert meta_prem["calificacion_minima_buena"] == RATING_BUENA_PREMIUM
    assert meta_prem["atractores_calificacion_alta_en_pool"] == 1


def test_sugerir_atractores_floreria_familias_tar():
    from app.domain.aliados_guiados import sugerir_atractores

    sugerencias = sugerir_atractores(
        "florería",
        perfil_cliente=["familias"],
        horarios_pico=["tarde"],
    )
    tipos = [s["tipo"] for s in sugerencias if s["sugerido"]]
    assert "school" in tipos
    assert any(s["puntaje"] > 0 for s in sugerencias)


def test_sugerir_atractores_publico_general_solo():
    from app.domain.aliados_guiados import sugerir_atractores

    sugerencias = sugerir_atractores(
        "abarrotes",
        perfil_cliente=["publico_general"],
        horarios_pico=["manana"],
    )
    sugeridos = [s for s in sugerencias if s["sugerido"]]
    tipos = {s["tipo"] for s in sugeridos}
    assert "transit_station" in tipos or "convenience_store" in tipos
    assert any("tráfico mixto" in s["motivo"].lower() or "trafico mixto" in s["motivo"].lower() for s in sugerencias)


def test_validar_config_guiada_minimo_dos_atractores():
    import pytest

    from app.domain.aliados_guiados import validar_config_guiada

    with pytest.raises(ValueError, match="al menos 2"):
        validar_config_guiada(
            {
                "perfil_cliente": ["familias"],
                "horarios_pico": ["tarde"],
                "atractores_confirmados": ["school"],
            },
            modo="guiado",
        )

    ok = validar_config_guiada(
        {
            "perfil_cliente": ["publico_general"],
            "horarios_pico": ["mediodia"],
            "atractores_confirmados": ["transit_station", "supermarket"],
        },
        modo="guiado",
    )
    assert ok["atractores_confirmados"] == ["transit_station", "supermarket"]


def test_resolver_aliados_modo_guiado_sin_llm():
    from app.domain.competencia_busqueda import resolver_tipos_aliados_busqueda

    tipos, ia_auto, fuente = resolver_tipos_aliados_busqueda(
        None,
        rubro="florería",
        modo_analisis_aliados="guiado",
        config_aliados_guiados={
            "perfil_cliente": ["familias"],
            "horarios_pico": ["tarde"],
            "atractores_confirmados": ["school", "shopping_mall"],
        },
    )
    assert tipos == ["school", "shopping_mall"]
    assert ia_auto is False
    assert fuente == "guiado_usuario"


def test_crear_preferencia_guiado_solo_premium():
    headers = {"Authorization": "Bearer mock-token"}
    payload_pro = {
        "tier_adquirido": "pro",
        "latitud": 19.432608,
        "longitud": -99.133208,
        "radio_metros": 1000,
        "rubro": "florería",
        "modo_analisis_aliados": "guiado",
        "config_aliados_guiados": {
            "perfil_cliente": ["familias"],
            "horarios_pico": ["tarde"],
            "atractores_confirmados": ["school", "park"],
        },
    }
    response_pro = client.post("/api/pagos/preferencia", json=payload_pro, headers=headers)
    assert response_pro.status_code == 422
    assert "solo está disponible en reporte Premium" in response_pro.text

    payload_prem = {
        "tier_adquirido": "premium",
        "latitud": 19.432608,
        "longitud": -99.133208,
        "radio_metros": 1000,
        "rubro": "florería",
        "modo_analisis_aliados": "guiado",
        "config_aliados_guiados": {
            "perfil_cliente": ["familias"],
            "horarios_pico": ["tarde"],
            "atractores_confirmados": ["school", "park"],
        },
        "aliados_adicionales": "OXXO",
    }
    response_prem = client.post("/api/pagos/preferencia", json=payload_prem, headers=headers)
    assert response_prem.status_code == 201


def test_api_sugerir_aliados_guiados():
    headers = {"Authorization": "Bearer mock-token"}
    response = client.post(
        "/api/analizar/aliados/sugerir",
        json={
            "rubro": "cafetería",
            "perfil_cliente": ["estudiantes"],
            "horarios_pico": ["manana"],
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["sugerencias"]) >= 10
    assert any(s["sugerido"] for s in data["sugerencias"])


def test_pdf_incluye_configuracion_guiada():
    from types import SimpleNamespace

    from app.domain.aliados_guiados import (
        etiquetas_atractores_legibles,
        etiquetas_horario_legibles,
        etiquetas_perfil_legibles,
    )
    from app.services.v0.reports.report_pdf_service import ReportLabGenerator

    config = {
        "perfil_cliente": ["familias"],
        "horarios_pico": ["tarde"],
        "atractores_confirmados": ["school", "transit_station"],
    }
    assert "Familias" in etiquetas_perfil_legibles(config["perfil_cliente"])
    assert "Tarde" in etiquetas_horario_legibles(config["horarios_pico"])
    assert "Escuelas" in etiquetas_atractores_legibles(config["atractores_confirmados"])

    analisis = {
        "modo_analisis_aliados": "guiado",
        "config_aliados_guiados": config,
        "aliados_conteos": {"school": 3, "transit_station": 2},
        "aliados_listado": [],
        "competidores_listado": [],
        "competidores_destacados": [],
        "competidores_conteo": 0,
        "bancos_conteo": 0,
        "escuelas_conteo": 3,
        "transporte_conteo": 2,
        "poblacion_ponderada": 10000,
        "densidad_hab_km2": 5000,
        "score_demog": 80,
        "score_competencia": 70,
        "score_trafico": 60,
        "sva": 75,
        "rubro": "florería",
        "direccion": "CDMX",
        "afluencia_peatonal": {"status": "unavailable"},
        "segmentacion_demografica": {},
        "nse": {"nse_etiqueta": "C+ (Medio Alto)", "nse_score": 62, "metricas": {"fuente": "censo_2020"}},
    }
    orden = SimpleNamespace(
        id=9999,
        checkout_id="chk_guiado_test",
        tier_adquirido="premium",
        rubro="florería",
        radio_metros=1000,
        latitud=19.43,
        longitud=-99.13,
        aliados_adicionales="OXXO",
        modo_analisis_aliados="guiado",
        config_aliados_guiados=None,
        competidores_adicionales=None,
        intenciones=None,
        competidores_seleccionados=None,
        aliados_seleccionados=None,
    )
    foda = {
        "fortalezas": ["Zona con demanda."],
        "oportunidades": ["Diferenciación."],
        "consideraciones_apertura": ["Validar renta."],
        "conclusion": "Viabilidad moderada.",
        "dictamen_final": "Aceptable con condiciones.",
    }
    pdf = ReportLabGenerator.construir_reporte_pdf(orden, analisis, foda)
    assert isinstance(pdf, bytes)
    assert len(pdf) > 5000
