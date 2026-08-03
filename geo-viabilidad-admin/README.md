# Geo Viabilidad — Admin

Panel Flask: dashboard, órdenes, leads, ingesta INEGI.

**Versión:** `1.0.0` (`VERSION` + `pyproject.toml`).

## Arranque

```powershell
cd geo-viabilidad-admin
uv sync --group dev
uv run flask --app admin.app:app run --host 0.0.0.0 --port 8501
```

URL local: http://localhost:8501/admin/login

Con Docker Compose desde la raíz del monorepo: `./run_local.ps1` (servicio admin en `:8501`).

## Dependencias (`uv`)

Fuente de verdad: `pyproject.toml` + `uv.lock`.

`geo-viabilidad-data` se resuelve como path editable (`../geo-viabilidad-data`) vía `[tool.uv.sources]`.

```powershell
uv sync --group dev
```

## Calidad

```powershell
uv run ruff check admin tests
uv run ruff format admin tests
uv run pytest tests/ -q
```

## Fuentes INEGI

Colocar shapefiles/CSV en `fuentes/` (gitignored).
