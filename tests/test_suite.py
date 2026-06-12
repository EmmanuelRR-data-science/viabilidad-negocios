import os
import sys
from decimal import Decimal

from fastapi.testclient import TestClient

# Configure python path to resolve imports from root directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.analytics import (
    calcular_distancia_haversine,
    calcular_score_demografico,
    resolver_competidores_destacados_para_reporte,
    resolver_google_type,
)
from app.google_places import competidor_es_relevante_al_giro, filtrar_competidores_por_giro
from app.nse import (
    calcular_nse,
    construir_nse_fallback,
    derivar_metricas_fallback,
    etiqueta_desde_score,
    hash_nse_fallback,
    nse_score_desde_metricas,
)
from app.database import SessionLocal
from app.main import app
from app.models import OrdenPago

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
    Test that the health check endpoint is functional and reports 'online'.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "GeoViabilidad Hook" in data["service"]


def test_exception_middleware_db():
    """
    Test that database connection errors (OperationalError) are caught by the
    UserFriendlyExceptionMiddleware and translated to a user-friendly message.
    """
    response = client.get("/error-test?tipo=db")
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
    response = client.get("/error-test?tipo=aws")
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
    response = client.get("/error-test?tipo=unexpected")
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
        assert nse["metricas"]["fuente"] in {"censo_2020", "fallback_determinista"}
    finally:
        db.close()


def test_segmentacion_demografica_con_db():
    from app.demografia_segmentos import calcular_segmentacion_demografica

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
    from app.competencia_busqueda import resolver_tipos_competidores_busqueda

    tipos, _, fuente = resolver_tipos_competidores_busqueda(
        ["cafe", "bakery", "ia_auto"],
        rubro="cafetería gourmet",
        google_type="cafe",
        categorias_ia={"competidores": ["restaurant"], "aliados": []},
    )
    assert fuente == "categorias_usuario"
    assert tipos == ["cafe", "bakery"]


def test_resolver_competidores_ia_usa_rubro_sin_categorias_manuales():
    from app.competencia_busqueda import keyword_places_para_ia, resolver_tipos_competidores_busqueda

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
        intenciones="tienda de collares y juguetes para perros",
        google_type="store",
    )
    assert kw is not None
    assert "mascotas" in kw.lower() or "collares" in kw.lower()


def test_nombre_categoria_places_en_espanol():
    from app.aliados_deterministico import nombre_categoria_places

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
    from app.competencia_busqueda import keyword_places_para_ia

    kw = keyword_places_para_ia(
        "florería",
        intenciones="florería que venda al público en general",
        google_type="store",
    )
    assert kw == "florería que venda al público en general"


def test_keyword_ia_ignora_intenciones_placeholder_y_usa_rubro():
    from app.competencia_busqueda import keyword_places_para_ia

    kw = keyword_places_para_ia(
        "florería",
        intenciones="Evaluación comercial del giro en la zona residencial mexicana.",
        google_type="store",
    )
    assert kw == "florería"


def test_resolver_aliados_matriz_cafeteria():
    from app.aliados_deterministico import resolver_aliados_por_rubro
    from app.competencia_busqueda import resolver_tipos_aliados_busqueda

    tipos, ia_auto, fuente = resolver_tipos_aliados_busqueda(
        ["ia_auto"],
        rubro="cafetería de especialidad",
    )
    assert fuente == "matriz_rubro"
    assert ia_auto is True
    assert tipos == ["school", "transit_station", "bank", "shopping_mall"]
    assert resolver_aliados_por_rubro("café gourmet") == tipos


def test_resolver_aliados_matriz_farmacia():
    from app.competencia_busqueda import resolver_tipos_aliados_busqueda

    tipos, _, fuente = resolver_tipos_aliados_busqueda(
        ["ia_auto"],
        rubro="farmacia de barrio",
    )
    assert fuente == "matriz_rubro"
    assert tipos == ["doctor", "supermarket", "transit_station", "convenience_store"]


def test_resolver_aliados_matriz_mascotas():
    from app.competencia_busqueda import resolver_tipos_aliados_busqueda

    tipos, _, fuente = resolver_tipos_aliados_busqueda(
        ["ia_auto"],
        rubro="accesorios para mascotas",
    )
    assert fuente == "matriz_rubro"
    assert "supermarket" in tipos
    assert "park" in tipos


def test_resolver_aliados_matriz_default_sin_rubro_conocido():
    from app.competencia_busqueda import resolver_tipos_aliados_busqueda

    tipos, _, fuente = resolver_tipos_aliados_busqueda(
        ["ia_auto"],
        rubro="servicios profesionales varios",
    )
    assert fuente == "matriz_rubro"
    assert tipos == ["transit_station", "school", "bank"]


def test_resolver_aliados_intenciones_reordenan_sin_agregar():
    from app.aliados_deterministico import resolver_aliados_por_rubro

    base = resolver_aliados_por_rubro("cafetería")
    con_escuela = resolver_aliados_por_rubro(
        "cafetería",
        intenciones="cerca de escuela primaria y colegio",
    )
    assert set(con_escuela) == set(base)
    assert con_escuela[0] == "school"


def test_sva_calculo_transparente_y_simulador():
    from app.sva_calculo import (
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

    _, sva_calc = componer_sva(72.2, score_comp, 55.0)
    assert sva_calc == 62


def test_competidores_mas_cercanos_y_lectura():
    from app.analytics import (
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
    assert "friccion directa" in lectura_competidor_cercano(
        {"rating": 4.8, "user_ratings_total": 120}
    ).lower()
    assert "aceptable" in lectura_competidor_cercano(lista[2]).lower()


def test_lectura_estrategica_enriquecimiento_y_conclusion():
    from app.lectura_estrategica import (
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

    conclusion_html = generar_conclusion_detallada(
        analisis, "Cafetería", tier="pro", radio_metros=1000, html=True
    )
    assert "<b>" in conclusion_html

    bloques = bloques_metodologia_resumen(analisis, tier="pro", radio_metros=1000)
    assert any("ISC" in t for t, _ in bloques)
    assert any("Nivel socioeconómico" in t for t, _ in bloques)


def test_interpretacion_demografia_por_rubro():
    from app.reports import _interpretacion_distribucion_poblacional

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
    from app.aliados_deterministico import resolver_aliados_por_rubro
    from app.competencia_busqueda import resolver_tipos_aliados_busqueda

    tipos, _, fuente = resolver_tipos_aliados_busqueda(
        ["ia_auto"],
        rubro="florería boutique",
    )
    assert fuente == "matriz_rubro"
    assert tipos == ["shopping_mall", "school", "doctor", "restaurant"]

    con_hospital = resolver_aliados_por_rubro(
        "florería",
        intenciones="arreglos para hospital y condolencias",
    )
    assert con_hospital[0] == "doctor"
    assert set(con_hospital) == set(tipos)


def test_resolver_aliados_prioriza_categorias_usuario():
    from app.competencia_busqueda import resolver_tipos_aliados_busqueda

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
    headers = {"Authorization": "Bearer test-jwt-token"}
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
    headers = {"Authorization": "Bearer test-jwt-token"}
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
            intenciones="Cafetería gourmet",
        )
        db.add(orden)
        db.commit()
        db.refresh(orden)

        # Trigger mock webhook to approve the payment
        webhook_payload = {"checkout_id": checkout_id, "estado_pago": "approved"}
        response = client.post("/api/pagos/webhook-mock", json=webhook_payload)
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
    headers = {"Authorization": "Bearer test-jwt-token"}

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
    assert "El Tier Básico permite un máximo de 1 competidor" in response.text

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
    assert "El Tier Básico no permite personalizar aliados" in response2.text


def test_crear_preferencia_invalida_pro_aliados():
    """
    Test that Pro tier rejects custom allies.
    """
    headers = {"Authorization": "Bearer test-jwt-token"}
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
    assert "El Tier Pro no permite personalizar aliados" in response.text


def test_crear_preferencia_invalida_pro_limites():
    """
    Test that Pro tier rejects more than 3 custom competitors.
    """
    headers = {"Authorization": "Bearer test-jwt-token"}
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
    assert "El Tier Pro permite un máximo de 3 competidores" in response.text


def test_crear_preferencia_invalida_premium_limites():
    """
    Test that Premium tier rejects more than 5 custom competitors or allies.
    """
    headers = {"Authorization": "Bearer test-jwt-token"}
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
    assert "El Tier Premium permite un máximo de 5 competidores" in response.text

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
    assert "El Tier Premium permite un máximo de 5 aliados" in response2.text


def test_crear_preferencia_valida_pro_premium():
    """
    Test successful creation of Pro and Premium preferences with custom selections.
    """
    headers = {"Authorization": "Bearer test-jwt-token"}
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
            intenciones="Cafetería gourmet",
            resultado_json=json.dumps(cached_resultado),
            foda_json=json.dumps(cached_foda),
        )
        db.add(orden)
        db.commit()
        db.refresh(orden)

        # Retrieve the analysis result
        headers = {"Authorization": "Bearer test-jwt-token"}
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
            intenciones="Florería premium",
            s3_key_reporte=f"informes/usr_mock_123/{checkout_id}_reporte_floreria.pdf",
        )
        db.add(orden)
        db.commit()
        db.refresh(orden)

        # 1. Get the download URL (requires auth headers)
        headers = {"Authorization": "Bearer test-jwt-token"}
        response = client.get(f"/api/analizar/pdf/{orden.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert f"/api/analizar/pdf/{orden.id}/descargar" in data["url_descarga"]

        # Create dummy PDF file locally
        os.makedirs("scratch/reports", exist_ok=True)
        local_pdf = f"scratch/reports/{checkout_id}_reporte_floreria.pdf"
        with open(local_pdf, "w") as f:
            f.write("dummy pdf content")

        try:
            # 2. Access download URL (should NOT require auth headers)
            dl_response = client.get(f"/api/analizar/pdf/{orden.id}/descargar")
            assert dl_response.status_code == 200
            assert dl_response.headers["content-type"] == "application/pdf"
            assert (
                'attachment; filename="Reporte_Viabilidad_floreria.pdf"' in dl_response.headers["content-disposition"]
            )
            assert dl_response.text == "dummy pdf content"
        finally:
            if os.path.exists(local_pdf):
                os.remove(local_pdf)

        # Clean up database
        db.delete(orden)
        db.commit()
    finally:
        db.close()


def test_procesar_calculo_analitico_aliados_adicionales():
    """
    Test that procesar_calculo_analitico handles text-input additional allies (aliados_adicionales)
    by performing keyword-based Places searches and enriching the allies list.
    """
    from app.analytics import procesar_calculo_analitico

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


def test_buscar_direccion_api():
    """
    Test that the search endpoint `/api/analizar/buscar-direccion` works
    correctly and returns mock coordinates in DEV_MODE.
    """
    headers = {"Authorization": "Bearer test-jwt-token"}
    response = client.get("/api/analizar/buscar-direccion?direccion=Reforma%20222", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["resultados"]) > 0
    assert "latitud" in data["resultados"][0]
    assert "longitud" in data["resultados"][0]
    assert "direccion" in data["resultados"][0]
    assert "Reforma 222" in data["resultados"][0]["direccion"]


def test_sugerir_atractores_floreria_familias_tar():
    from app.aliados_guiados import sugerir_atractores

    sugerencias = sugerir_atractores(
        "florería",
        perfil_cliente=["familias"],
        horarios_pico=["tarde"],
    )
    tipos = [s["tipo"] for s in sugerencias if s["sugerido"]]
    assert "school" in tipos
    assert any(s["puntaje"] > 0 for s in sugerencias)


def test_sugerir_atractores_publico_general_solo():
    from app.aliados_guiados import sugerir_atractores

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
    from app.aliados_guiados import validar_config_guiada
    import pytest

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
    from app.competencia_busqueda import resolver_tipos_aliados_busqueda

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
    headers = {"Authorization": "Bearer test-jwt-token"}
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
    assert "solo está disponible en Tier Premium" in response_pro.text

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
    headers = {"Authorization": "Bearer test-jwt-token"}
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

    from app.aliados_guiados import (
        etiquetas_atractores_legibles,
        etiquetas_horario_legibles,
        etiquetas_perfil_legibles,
    )
    from app.reports import ReportLabGenerator

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
