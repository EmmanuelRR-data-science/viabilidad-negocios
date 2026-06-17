# GeoViabilidad Hook

Plataforma de análisis de viabilidad comercial geoespacial para México. Combina datos demográficos del INEGI, competencia y aliados vía Google Places, afluencia peatonal de BestTime y razonamiento estratégico con LLMs (AWS Bedrock / Groq) para generar dictámenes de viabilidad y reportes PDF por niveles (Básico, Pro y Premium).

## Stack

- **Backend**: FastAPI (Python 3.11), SQLAlchemy, PostgreSQL + PostGIS
- **Frontend**: SPA estática (HTML/CSS/JS) servida por FastAPI
- **Consola administrativa**: Streamlit (ingesta de shapefiles INEGI y dashboard)
- **IA**: AWS Bedrock (Llama 3 70B) con fallback a Groq
- **Integraciones**: Google Places/Geocoding, BestTime, Mercado Pago (Checkout Pro), AWS S3/SES
- **Reportes**: ReportLab (PDF)

## Requisitos

- Docker y Docker Compose
- Una base de datos PostgreSQL + PostGIS accesible en la red `geoanalisis-sdd_geo-network` (red externa de Docker)
- Llaves de API (opcionales en `DEV_MODE=True`, que simula Cognito y Mercado Pago)

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
| Consola administrativa (Streamlit) | http://localhost:8501 |

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
admin_app.py        # Consola administrativa Streamlit
ingest_all_states.py# Ingesta masiva de shapefiles INEGI
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
