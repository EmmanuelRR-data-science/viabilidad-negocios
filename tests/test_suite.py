import os
import sys
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

# Configure python path to resolve imports from root directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal
from app.models import OrdenPago
from app.analytics import calcular_distancia_haversine, resolver_google_type

client = TestClient(app)

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
        "intenciones": "Quiero poner una cafetería de especialidad."
    }
    # Bearer authentication header is required, even if simulated in DEV_MODE
    headers = {"Authorization": "Bearer test-jwt-token"}
    response = client.post("/api/pagos/preferencia", json=payload, headers=headers)
    assert response.status_code == 201
    
    data = response.json()
    assert "orden_id" in data
    assert data["monto"] == 99.00
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
            monto=Decimal("249.00"),
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
        webhook_payload = {
            "checkout_id": checkout_id,
            "estado_pago": "approved"
        }
        response = client.post("/api/pagos/webhook-mock", json=webhook_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["orden_id"] == orden.id
        
        # Verify the webhook updates the payment state and launches tasks (tested in DEV_MODE synchronously)
        db.refresh(orden)
        assert orden.estado_pago == "approved"
        assert orden.s3_key_reporte is not None

        # Clean up database entry and generated reports/emails
        db.delete(orden)
        db.commit()

        local_pdf = f"scratch/reports/{checkout_id}_reporte.pdf"
        if os.path.exists(local_pdf):
            os.remove(local_pdf)
            
        local_email = f"scratch/emails/email_orden_{orden.id}.html"
        if os.path.exists(local_email):
            os.remove(local_email)

    finally:
        db.close()
