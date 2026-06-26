# GeoViabilidad Hook

Plataforma de análisis de viabilidad comercial geoespacial para México. Combina datos demográficos del INEGI, competencia y aliados vía Google Places, afluencia peatonal de BestTime y razonamiento estratégico con LLMs (AWS Bedrock / Groq) para generar dictámenes de viabilidad y reportes PDF por niveles (Básico, Pro y Premium).

## Stack

- **Backend**: FastAPI (Python 3.11), SQLAlchemy, PostgreSQL + PostGIS
- **Frontend**: SPA estática (HTML/CSS/JS) servida por FastAPI
- **Consola administrativa**: Flask (`admin/`, puerto 8501): leads, órdenes e ingesta INEGI
- **IA**: AWS Bedrock (Llama 3 70B) con fallback a Groq
- **Integraciones**: Google Places/Geocoding, BestTime, Mercado Pago (Checkout Pro), AWS S3/SES
- **Reportes**: ReportLab (PDF)

## Requisitos

- Docker y Docker Compose
- Llaves de API (opcionales en `DEV_MODE=True`, que simula Cognito y Mercado Pago)

El `docker-compose.yml` incluye PostgreSQL + PostGIS (`geo-analisis-db`, puerto host `5435`). No hace falta un repositorio aparte para la base de datos.

**Primera vez / despliegue limpio:** con PostGIS arriba (`docker compose up -d geo-db`), restaura la demografía nacional incluida en el repo:

```bash
# Linux / macOS / Git Bash
bash scripts/restore_demografia_local.sh

# Windows (PowerShell)
./scripts/restore_demografia_local.ps1
```

Ver `backups/MANIFEST.json` para cobertura (32 entidades, ~64k AGEBs).

## Inicio rápido

1. Copiar la plantilla de variables de entorno y llenar las llaves:

```bash
cp .env.example .env
```

2. Levantar los servicios:

```bash
# Windows
./run_local.ps1

# Linux / macOS
./run_local.sh
```

3. Acceder a los servicios:

| Servicio | URL |
|---|---|
| API + SPA pública | http://localhost:8000 |
| Documentación OpenAPI | http://localhost:8000/docs |
| Consola administrativa (Flask) | http://localhost:8501/admin/login |

## Variables de entorno

Ver `.env.example` para la lista completa. Las principales:

| Variable | Descripción |
|---|---|
| `DB_*` | Conexión a PostgreSQL/PostGIS |
| `DEV_MODE` | `True` activa simulaciones locales (Cognito, Mercado Pago) |
| `BEDROCK_MODEL_ID` | Modelo de AWS Bedrock a invocar |
| `GOOGLE_PLACES_API_KEY` | Google Places y Geocoding |
| `BEST_TIME_API_KEY` | Afluencia peatonal BestTime |
| `GROQ_API_KEY` / `GROQ_MODEL` | LLM alternativo para entorno de pruebas |
| `MERCADOPAGO_ACCESS_TOKEN` | Checkout Pro (sandbox o producción) |

> **Nunca** subas el archivo `.env` al repositorio. Está ignorado por `.gitignore`.

## Estructura del proyecto

```
app/                # Backend FastAPI (analytics, bedrock, payments, reports, etc.)
frontend/           # SPA pública (index.html, app.js, index.css)
admin/              # Panel administrativo Flask (leads, órdenes, ingesta INEGI)
ingest_all_states.py# Ingesta masiva de shapefiles INEGI (CLI)
tests/              # Suite de pruebas (incluye tests de seguridad LLM)
fuentes/            # Datos crudos INEGI (ignorado en git)
scratch/            # Experimentos y scripts de depuración (ignorado en git)
```

## Pruebas

```bash
pytest tests/test_suite.py          # Suite principal
pytest tests/security/              # Stress tests de seguridad del LLM
```

## Ingesta de datos INEGI

Colocar los shapefiles por estado en `fuentes/` y usar la consola administrativa (puerto 8501) o el script masivo:

```bash
python ingest_all_states.py
```
