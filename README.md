# Geo Viabilidad Negocios

Monorepo del producto **GeoViabilidad**: análisis de viabilidad comercial geoespacial para México.

Este README es el **runbook del equipo** (Pedro / Luis / Miguel / quien clone el repo): cómo levantar, probar y validar el stack sin depender de AWS.

Funciona en **Linux, macOS y Windows** (Docker es el camino principal). Los ejemplos de shell usan **bash**; al final hay equivalentes PowerShell.

---

## Requisitos

| Herramienta | Para qué |
|-------------|----------|
| **Docker** + Compose v2 | Stack completo (PostGIS, API, SPA, Admin) |
| **bash** | `./run_local.sh` (Linux / macOS / WSL) |
| **uv** ([instalar](https://docs.astral.sh/uv/)) | Tests / desarrollo Python fuera de Docker |

Opcional para flujo “completo” en local: claves `GOOGLE_MAPS` / `GOOGLE_OAUTH`, `GROQ_API_KEY`. Con `PAYMENTS_MOCK=true` **no** hace falta Mercado Pago ni AWS.

> **Windows nativo:** puedes usar `./run_local.ps1` o WSL + `./run_local.sh`. Los scripts de demografía/INEGI son solo `.sh`.

---

## Mapa del monorepo

| Carpeta | Rol | Puerto local |
|---------|-----|--------------|
| `geo-viabilidad-web/` | SPA (HTML/CSS/JS) vía nginx | **8000** |
| `geo-viabilidad-api/` | Backend FastAPI + motor analítico | **8001** (Swagger/docs) |
| `geo-viabilidad-admin/` | Panel Flask (órdenes, leads, ingesta) | **8501** |
| `geo-viabilidad-data/` | Paquete compartido ORM / PostGIS / INEGI | librería (`uv`) |

Versiones de producto (SemVer):

- API / Admin / Web: ver `*/VERSION` (API alineada a **1.0.0**)
- Data: `geo-viabilidad-data/VERSION` (**0.1.0**)

---

## Arranque en 3 pasos (camino feliz)

### 1. Variables de entorno

```bash
cd geo-viabilidad-negocios
cp .env.example .env
```

Valores **recomendados para local** (ya vienen en `.env.example`):

| Variable | Valor local | Nota |
|----------|-------------|------|
| `DEV_MODE` | `true` | Sin AWS obligatorio |
| `PAYMENTS_MOCK` | `true` | Checkout simulado |
| `REPORTS_LOCAL_STORAGE` | `true` | PDF en disco |
| `LLM_PROVIDER` | `groq` | Alternativas: `openai`, `bedrock` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `PhiQus` / `viabilidad-negocios` | Gate SPA + Admin |

Para Places / OAuth / FODA con LLM, completa en `.env`:

- `GOOGLE_PLACES_API_KEY` o `GOOGLE_MAPS_API_KEY`
- `GOOGLE_OAUTH_CLIENT_ID` (login Google en la SPA)
- `GROQ_API_KEY` (si `LLM_PROVIDER=groq`)

### 2. Levantar el stack

```bash
chmod +x run_local.sh   # solo la primera vez
./run_local.sh
```

Eso hace `docker compose build` + `up -d` (PostGIS, API, SPA, Admin).  
La primera vez puede tardar varios minutos (build de imágenes + GDAL).

### 3. Abrir y comprobar

| Qué | URL |
|-----|-----|
| **App (SPA)** | http://localhost:8000 |
| **Swagger / OpenAPI** | http://localhost:8001/docs |
| **Health API** | http://localhost:8001/health |
| **Admin** | http://localhost:8501/admin/login |

**Puerta PhiQus** (SPA y Admin):

| Campo | Valor |
|-------|-------|
| Usuario | `PhiQus` |
| Contraseña | `viabilidad-negocios` |

Smoke rápido:

```bash
curl http://localhost:8001/health
# → JSON con "status": "online" (HTTP 200)
```

En Swagger: `GET /api/pagos/config` (con mock no exige MP real).

---

## Datos demográficos (primera vez / BD vacía)

Sin tablas censales el análisis cuantitativo no tiene población/NSE reales.

Con el stack arriba (`geo-db` healthy):

```bash
# Requiere Git LFS (el dump ~67 MB no va en el blob de Git)
git lfs install
git lfs pull
bash ./geo-viabilidad-api/scripts/demografia/restore_demografia_local.sh
```

Detalle de scripts: [`geo-viabilidad-api/scripts/README.md`](geo-viabilidad-api/scripts/README.md).

---

## Flujo de prueba sugerido (sin front-expertise)

1. http://localhost:8000 → login PhiQus.
2. Marcar un punto en CDMX, elegir giro (ej. Cafetería), **Analizar**.
3. Con `PAYMENTS_MOCK=true`, comprar un plan y validar que el PDF se genera / descarga.
4. Alternativa solo API: usar Swagger en `:8001/docs` (health, pagos/config, endpoints de análisis según contrato).

Guía paso a paso del producto: [`docs/GUIA_USO_LOCAL.md`](docs/GUIA_USO_LOCAL.md)  
Guía para testers no técnicos: [`docs/GUIA_PRUEBAS_USUARIO.md`](docs/GUIA_PRUEBAS_USUARIO.md)

---

## Tests y calidad (Python)

```bash
# API
cd geo-viabilidad-api
uv sync --group dev
uv run ruff check app tests scripts
uv run pytest tests/ -q --ignore=tests/security

# Admin
cd ../geo-viabilidad-admin
uv sync --group dev
uv run ruff check admin tests
uv run pytest tests/ -q

# Data (lint)
cd ../geo-viabilidad-data
uv sync --group dev
uv run ruff check geo_viabilidad_data
```

Debug del motor **sin IA** (JSON + Excel): ver sección en [`geo-viabilidad-api/README.md`](geo-viabilidad-api/README.md) (`scripts/debug_analisis_cuantitativo.py`).

---

## Parar / reiniciar

```bash
docker compose down          # para contenedores (conserva volumen PostGIS)
docker compose up -d         # vuelve a levantar
./run_local.sh               # rebuild + up
docker compose logs -f web-api
docker compose logs -f admin-app
```

---

## Arquitectura y docs

| Documento | Contenido |
|-----------|-----------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Árbol y endpoints |
| [`docs/REPO_SPLIT_AND_LAYERS.md`](docs/REPO_SPLIT_AND_LAYERS.md) | Plan multi-repo / capas |
| [`rfcs/rfc-api-layers.md`](rfcs/rfc-api-layers.md) | Capas API (routers → services → clients) |
| [`geo-viabilidad-api/README.md`](geo-viabilidad-api/README.md) | Runbook API, LLM_PROVIDER, Commitizen |
| [`geo-viabilidad-admin/README.md`](geo-viabilidad-admin/README.md) | Runbook Admin |
| [`geo-viabilidad-data/README.md`](geo-viabilidad-data/README.md) | Paquete data compartido |

**Dependencias Python:** solo `pyproject.toml` + `uv.lock` (sin inventario `requirements.txt`). Docker usa `uv sync --frozen`.

---

## Windows (PowerShell) — equivalentes

```powershell
Copy-Item .env.example .env
./run_local.ps1
curl http://localhost:8001/health
```

Demografía: usar **WSL** o Git Bash con el mismo `.sh` de arriba.  
Si `uv sync` falla por OneDrive/hardlinks: los `pyproject.toml` ya usan `link-mode = copy`; borra `.venv` y reintenta.

---

## Problemas frecuentes

| Síntoma | Qué revisar |
|---------|-------------|
| `run_local.sh` / build falla | Docker corriendo; espacio en disco; logs del build API (GDAL) |
| SPA en `:8000` pero docs 404 | Swagger está en **`:8001/docs`**, no en `:8000` |
| Análisis sin población / NSE | Restaurar demografía (sección arriba) |
| Login Google no abre | `GOOGLE_OAUTH_CLIENT_ID` en `.env` + orígenes autorizados |
| FODA vacío / sin narrativa IA | `LLM_PROVIDER=groq` + `GROQ_API_KEY` válida |
| Pagos “reales” en local | Dejar `PAYMENTS_MOCK=true`; MP sandbox necesita HTTPS/`PUBLIC_APP_URL` |
| Permiso denegado en `./run_local.sh` | `chmod +x run_local.sh` |

---

## Nota histórica

Este monorepo proviene de `viabilidad-hook` (reorganización 2026). Trabajar siempre sobre **`geo-viabilidad-negocios`**.
