"""Pruebas del panel administrativo Flask."""

from admin.app import create_app


def _login(client):
    return client.post(
        "/admin/login",
        data={"username": "PhiQus", "password": "viabilidad-negocios"},
        follow_redirects=False,
    )


def test_admin_login_and_export_requires_auth():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        export_response = client.get("/admin/usuarios/export.xlsx")
        assert export_response.status_code == 302
        assert "/admin/login" in export_response.headers.get("Location", "")

        login_response = _login(client)
        assert login_response.status_code in (302, 303)

        dashboard = client.get("/admin/")
        assert dashboard.status_code == 200
        assert b"Ingresos aprobados" in dashboard.data

        export_ok = client.get("/admin/usuarios/export.xlsx")
        assert export_ok.status_code == 200
        assert export_ok.data[:2] == b"PK"


def test_admin_phase2_pages_and_filtered_exports():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        _login(client)

        usuarios = client.get("/admin/usuarios?compro=si&q=test")
        assert usuarios.status_code == 200
        assert b"Leads (usuarios Google)" in usuarios.data
        assert b"Descargar Excel filtrado" in usuarios.data

        ordenes = client.get("/admin/ordenes?estado=approved&tier=premium")
        assert ordenes.status_code == 200
        assert "Órdenes de pago".encode() in ordenes.data

        leads_export = client.get("/admin/usuarios/export.xlsx?compro=no")
        assert leads_export.status_code == 200
        assert leads_export.data[:2] == b"PK"

        orders_export = client.get("/admin/ordenes/export.xlsx?estado=pending")
        assert orders_export.status_code == 200
        assert orders_export.data[:2] == b"PK"


def test_admin_ingesta_page():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        _login(client)
        response = client.get("/admin/ingesta")
        assert response.status_code == 200
        assert b"Ingesta geoespacial" in response.data
        assert b"Ingesta masiva" in response.data
