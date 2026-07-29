"""Tests de arquitectura: verifican las fronteras entre capas.

Reglas validadas:
- Routers NO deben importar app.domain (excepto schemas)
- Routers NO deben importar app.clients (excepto get_db / Depends)
- Clients NO deben importar app.services (CERO excepciones)
- Domain NO debe importar app.clients ni sqlalchemy.orm.Session
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parent.parent / "app"

ALLOWED_ROUTER_CLIENT_IMPORTS = {"get_db"}
ALLOWED_ROUTER_DOMAIN_IMPORTS: set[str] = set()


def _collect_py_files(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*.py"))


def _extract_imports(filepath: Path) -> list[str]:
    """Extrae todos los nombres de módulo importados (from X import ... / import X)."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


class TestRoutersDoNotImportDomain:
    """Routers no deben importar app.domain directamente."""

    @pytest.fixture(params=_collect_py_files(API_ROOT / "routers"), ids=lambda p: str(p.relative_to(API_ROOT)))
    def router_file(self, request):
        return request.param

    def test_no_domain_import(self, router_file: Path):
        imports = _extract_imports(router_file)
        domain_imports = [m for m in imports if m.startswith("app.domain")]
        assert not domain_imports, (
            f"{router_file.relative_to(API_ROOT)} importa domain: {domain_imports}. "
            "Los routers deben delegar al servicio."
        )


class TestClientsDoNotImportServices:
    """Clients (app/clients/v0/) no deben importar app.services — CERO excepciones."""

    @pytest.fixture(
        params=_collect_py_files(API_ROOT / "clients" / "v0"),
        ids=lambda p: str(p.relative_to(API_ROOT)),
    )
    def client_file(self, request):
        return request.param

    def test_no_service_import(self, client_file: Path):
        imports = _extract_imports(client_file)
        svc_imports = [m for m in imports if m.startswith("app.services")]
        assert not svc_imports, (
            f"{client_file.relative_to(API_ROOT)} importa services: {svc_imports}. "
            "Los clients no deben depender de la capa de servicios."
        )


class TestDomainIsPure:
    """Domain no debe importar app.clients ni sqlalchemy.orm."""

    @pytest.fixture(
        params=_collect_py_files(API_ROOT / "domain"),
        ids=lambda p: str(p.relative_to(API_ROOT)),
    )
    def domain_file(self, request):
        return request.param

    def test_no_client_import(self, domain_file: Path):
        imports = _extract_imports(domain_file)
        client_imports = [m for m in imports if m.startswith("app.clients")]
        assert not client_imports, (
            f"{domain_file.relative_to(API_ROOT)} importa clients: {client_imports}. Domain debe ser puro — sin I/O."
        )

    def test_no_sqlalchemy_session(self, domain_file: Path):
        imports = _extract_imports(domain_file)
        sqla_imports = [m for m in imports if "sqlalchemy" in m]
        assert not sqla_imports, (
            f"{domain_file.relative_to(API_ROOT)} importa sqlalchemy: {sqla_imports}. "
            "Domain debe ser puro — sin Session."
        )


class TestExceptionsModuleExists:
    """Verifica que el módulo de excepciones existe y exporta las clases base."""

    def test_imports(self):
        from app.exceptions import (
            ExternalDependencyError,
            NotFoundError,
            UserFacingError,
        )

        assert issubclass(NotFoundError, UserFacingError)
        assert issubclass(ExternalDependencyError, UserFacingError)


class TestAuthSchemasCanonicalLocation:
    """auth_schemas vive en schemas/, no en routers/."""

    def test_canonical_import(self):
        from app.schemas.auth_schemas import GoogleAuthRequest

        assert GoogleAuthRequest is not None

    def test_no_routers_auth_schemas(self):
        """routers/auth_schemas.py must NOT exist — single home is schemas/."""
        import importlib

        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module("app.routers.auth_schemas")


class TestNoFlatClientOrReportShims:
    """Tras unificación v0: sin re-exports DEPRECATED en clients/ o services/ raíz."""

    FORBIDDEN_MODULES = (
        "app.clients.google_auth",
        "app.clients.google_places",
        "app.clients.besttime",
        "app.clients.bedrock",
        "app.clients.mercadopago_client",
        "app.services.report_pdf_service",
        "app.services.report_job_service",
    )

    @pytest.mark.parametrize("module_name", FORBIDDEN_MODULES)
    def test_shim_modules_removed(self, module_name: str):
        import importlib

        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module(module_name)

    def test_canonical_clients_and_reports_importable(self):
        from app.clients.v0.besttime import obtener_afluencia  # noqa: F401
        from app.clients.v0.google.google_auth import es_token_mock  # noqa: F401
        from app.clients.v0.mercadopago import crear_preferencia_checkout  # noqa: F401
        from app.services.v0.reports.report_job_service import generar_informe_task  # noqa: F401
        from app.services.v0.reports.report_pdf_service import ReportLabGenerator  # noqa: F401

        assert callable(es_token_mock)
        assert ReportLabGenerator is not None
        assert callable(generar_informe_task)
