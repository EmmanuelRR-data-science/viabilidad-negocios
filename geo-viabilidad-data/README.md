# geo-viabilidad-data

Paquete Python compartido: **ORM**, **conexión PostgreSQL/PostGIS** e **ingesta INEGI**.

Consumido por:

- `geo-viabilidad-api` (FastAPI)
- `geo-viabilidad-admin` (Flask)

**Versión:** `0.1.0` (`pyproject.toml`).

## Instalación

Fuente de verdad: `pyproject.toml` + `uv.lock`.

```powershell
cd geo-viabilidad-data
uv sync --group dev
```

En desarrollo, API y Admin lo declaran como path editable (`[tool.uv.sources]`); un `uv sync` en esos paquetes instala este módulo automáticamente.

## Calidad

```powershell
uv run ruff check geo_viabilidad_data
uv run ruff format geo_viabilidad_data
```

## Variables de entorno

`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DEV_MODE` (opcional, para SSL en RDS).
