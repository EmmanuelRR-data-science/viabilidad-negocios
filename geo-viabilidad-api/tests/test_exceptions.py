"""Tests para el mapeo de excepciones user-centric → HTTP responses."""

import pytest
from fastapi.testclient import TestClient

from app.exceptions import (
    ExternalDependencyError,
    ForbiddenError,
    NotFoundError,
    PaymentRequiredError,
    UserFacingError,
    ValidationUserError,
)


class TestExceptionHierarchy:
    """Verifica que los subtipos heredan de UserFacingError con status correcto."""

    @pytest.mark.parametrize(
        "exc_class,expected_status,expected_code",
        [
            (NotFoundError, 404, "not_found"),
            (PaymentRequiredError, 402, "payment_required"),
            (ForbiddenError, 403, "forbidden"),
            (ExternalDependencyError, 502, "external_dependency"),
            (ValidationUserError, 400, "validation_error"),
        ],
    )
    def test_subtypes_status_and_code(self, exc_class, expected_status, expected_code):
        exc = exc_class("Mensaje de prueba")
        assert isinstance(exc, UserFacingError)
        assert exc.status_code == expected_status
        assert exc.code == expected_code
        assert exc.message == "Mensaje de prueba"

    def test_base_defaults(self):
        exc = UserFacingError()
        assert exc.status_code == 500
        assert exc.code == "internal_error"
        assert exc.message == "Ha ocurrido un error inesperado."
        assert exc.suggested_action is None

    def test_suggested_action(self):
        exc = NotFoundError("No encontrado", suggested_action="Intenta con otro ID.")
        assert exc.suggested_action == "Intenta con otro ID."

    def test_custom_status_override(self):
        exc = ValidationUserError("Dato inválido", status_code=422)
        assert exc.status_code == 422


class TestExceptionHandler:
    """Verifica que el handler de FastAPI responde correctamente."""

    @pytest.fixture
    def client(self):
        from app.main import app

        return TestClient(app, raise_server_exceptions=False)

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_user_facing_error_via_handler(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.exceptions import NotFoundError, UserFacingError
        from app.main import user_facing_error_handler

        test_app = FastAPI()
        test_app.add_exception_handler(UserFacingError, user_facing_error_handler)

        @test_app.get("/fail")
        def fail():
            raise NotFoundError("Recurso no existe", suggested_action="Revisa el ID")

        tc = TestClient(test_app, raise_server_exceptions=False)
        resp = tc.get("/fail")
        assert resp.status_code == 404
        data = resp.json()
        assert data["friendly_message"] == "Recurso no existe"
        assert data["suggested_action"] == "Revisa el ID"
        assert "transaction_id" in data


class TestReportsServiceExceptions:
    """Verifica que las excepciones de reports_service heredan UserFacingError."""

    def test_orden_no_encontrada(self):
        from app.services.v0.reports.reports_service import OrdenNoEncontradaError

        exc = OrdenNoEncontradaError()
        assert isinstance(exc, NotFoundError)
        assert isinstance(exc, UserFacingError)
        assert exc.status_code == 404

    def test_acceso_no_autorizado(self):
        from app.services.v0.reports.reports_service import AccesoNoAutorizadoError

        exc = AccesoNoAutorizadoError()
        assert isinstance(exc, ForbiddenError)
        assert exc.status_code == 403

    def test_pago_no_acreditado(self):
        from app.services.v0.reports.reports_service import PagoNoAcreditadoError

        exc = PagoNoAcreditadoError()
        assert isinstance(exc, PaymentRequiredError)
        assert exc.status_code == 402
