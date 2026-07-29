"""Smoke de blindaje: endpoints sensibles rechazan acceso anónimo."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)

AUTH = {"Authorization": "Bearer mock-token"}

PROTECTED_GET = [
    "/error-test?tipo=db",
    "/api/analizar/debug/cuantitativo?lat=19.43&lng=-99.13",
    "/api/analizar/resultado/1",
    "/api/pagos/orden/1/estado",
    "/api/pagos/mi-ultima-aprobada",
    "/api/reportes/pdf/1",
]

PROTECTED_POST = [
    (
        "/api/analizar/aliados/sugerir",
        {"rubro": "cafeteria", "perfil_cliente": ["estudiantes"], "horarios_pico": ["manana"]},
    ),
    ("/api/pagos/webhook-mock", {"checkout_id": "chk_inexistente", "estado_pago": "approved"}),
]


def test_health_does_not_leak_env_flags():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "dev_mode" not in body
    assert "payments_mock" not in body


def test_protected_get_without_auth_returns_401():
    for path in PROTECTED_GET:
        resp = client.get(path)
        assert resp.status_code == 401, f"Expected 401 for GET {path}, got {resp.status_code}"


def test_protected_post_without_auth_returns_401():
    for path, payload in PROTECTED_POST:
        resp = client.post(path, json=payload)
        assert resp.status_code == 401, f"Expected 401 for POST {path}, got {resp.status_code}"


def test_pdf_descargar_requires_token_query():
    resp = client.get("/api/reportes/pdf/1/descargar")
    assert resp.status_code == 422


def test_openapi_response_models_are_objects_not_bare_string():
    schema = client.get("/api/openapi.json").json()
    paths_to_check = [
        ("/health", "get"),
        ("/api/pagos/config", "get"),
        ("/api/analizar/geocodificar", "get"),
        ("/api/reportes/pdf/{orden_id}", "get"),
        ("/api/auth/config", "get"),
    ]
    for path, method in paths_to_check:
        op = schema["paths"][path][method]
        content = op["responses"]["200"]["content"]["application/json"]
        ref_or_schema = content.get("schema", {})
        if "$ref" in ref_or_schema:
            continue
        assert ref_or_schema.get("type") != "string", f"{method.upper()} {path} still typed as string"


def test_error_test_requires_auth_even_in_dev():
    assert client.get("/error-test").status_code == 401
    assert client.get("/error-test?tipo=db", headers=AUTH).status_code == 500


def test_map_geocode_and_search_are_public():
    """El mapa necesita geocode/búsqueda antes del login (rate-limited)."""
    g = client.get("/api/analizar/geocodificar?lat=19.43&lng=-99.13")
    assert g.status_code == 200
    b = client.get("/api/analizar/buscar-direccion?direccion=Reforma")
    assert b.status_code == 200


def test_static_reports_not_mounted():
    resp = client.get("/static/reports/anything.pdf")
    assert resp.status_code == 404
