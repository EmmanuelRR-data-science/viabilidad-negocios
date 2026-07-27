# Estructura del Proyecto

Árbol de directorios del monorepo de **GeoViabilidad Negocios** (excluyendo entornos virtuales, cachés y archivos de Git).

```text
geo-viabilidad-negocios/
├── README.md
├── design.md
├── docker-compose.prod.yml
├── docker-compose.yml
├── docs
│   ├── ARCHITECTURE.md
│   └── REPO_SPLIT_AND_LAYERS.md
├── geo-viabilidad-admin
│   ├── Dockerfile
│   ├── README.md
│   ├── VERSION
│   ├── admin
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── routes.py
│   │   ├── services
│   │   │   ├── __init__.py
│   │   │   ├── filters.py
│   │   │   ├── ingest_dashboard.py
│   │   │   ├── ingest_flash_store.py
│   │   │   ├── ingest_manual.py
│   │   │   ├── leads_export.py
│   │   │   ├── metrics.py
│   │   │   ├── orders_query.py
│   │   │   └── schema_init.py
│   │   ├── static
│   │   │   └── admin.css
│   │   └── templates
│   │       ├── _macros.html
│   │       ├── _nav.html
│   │       ├── base.html
│   │       ├── dashboard.html
│   │       ├── ingesta.html
│   │       ├── login.html
│   │       ├── ordenes.html
│   │       └── usuarios.html
│   ├── fuentes
│   ├── requirements.txt
│   └── tests
│       ├── conftest.py
│       └── test_admin_flask.py
├── geo-viabilidad-api
│   ├── Dockerfile
│   ├── README.md
│   ├── VERSION
│   ├── app
│   │   ├── afluencia_presentacion.py
│   │   ├── aliados_deterministico.py
│   │   ├── aliados_guiados.py
│   │   ├── analytics.py
│   │   ├── assets
│   │   │   ├── cover_bg.png
│   │   │   ├── cover_logo.png
│   │   │   └── phiqus_logo_positivo.png
│   │   ├── auth.py
│   │   ├── bedrock.py
│   │   ├── besttime.py
│   │   ├── censo_segmentos_map.py
│   │   ├── chart_images.py
│   │   ├── clients
│   │   │   ├── __init__.py
│   │   │   ├── bedrock.py
│   │   │   ├── besttime.py
│   │   │   ├── google_places.py
│   │   │   └── mercadopago_client.py
│   │   ├── competencia_busqueda.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── demografia_segmentos.py
│   │   ├── domain
│   │   │   ├── __init__.py
│   │   │   ├── aliados_deterministico.py
│   │   │   ├── aliados_guiados.py
│   │   │   ├── competencia_busqueda.py
│   │   │   ├── demografia_segmentos.py
│   │   │   ├── nse.py
│   │   │   ├── seleccion_atractores.py
│   │   │   ├── sva_calculo.py
│   │   │   └── vigencia_comercio.py
│   │   ├── google_auth.py
│   │   ├── google_places.py
│   │   ├── infrastructure
│   │   │   ├── __init__.py
│   │   │   ├── database.py
│   │   │   └── models.py
│   │   ├── ingest_censo_helpers.py
│   │   ├── ingest_nacional.py
│   │   ├── ingest_shapefile_utils.py
│   │   ├── lectura_estrategica.py
│   │   ├── main.py
│   │   ├── map_image.py
│   │   ├── middleware.py
│   │   ├── models.py
│   │   ├── nse.py
│   │   ├── payments.py
│   │   ├── reports.py
│   │   ├── routers
│   │   │   ├── __init__.py
│   │   │   ├── analytics.py
│   │   │   ├── auth.py
│   │   │   ├── auth_schemas.py
│   │   │   └── payments.py
│   │   ├── routes_analytics.py
│   │   ├── routes_auth.py
│   │   ├── schemas.py
│   │   ├── schemas_aliados_guiados.py
│   │   ├── schemas_demografia.py
│   │   ├── schemas_nse.py
│   │   ├── seleccion_atractores.py
│   │   ├── services
│   │   │   ├── __init__.py
│   │   │   ├── aliados_guiados_service.py
│   │   │   ├── analytics_service.py
│   │   │   ├── auth_service.py
│   │   │   ├── payment_service.py
│   │   │   └── report_pdf_service.py
│   │   ├── sva_calculo.py
│   │   ├── tasks.py
│   │   ├── tiers
│   │   │   ├── __init__.py
│   │   │   ├── definitions.json
│   │   │   └── registry.py
│   │   └── vigencia_comercio.py
│   ├── docs
│   │   ├── ROADMAP.md
│   │   ├── SPEC_DRIVEN_CONTRACT_ALIADOS_GUIADOS.md
│   │   └── SPEC_DRIVEN_CONTRACT_NSE.md
│   ├── ingest_all_states.py
│   ├── ingest_censo_nse.py
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── scratch
│   │   ├── emails
│   │   ├── reports
│   │   └── security_reports
│   │       ├── security_report_20260702_112603.md
│   │       ├── security_report_20260702_112627.md
│   │       ├── security_report_20260702_113622.md
│   │       └── security_report_20260702_113645.md
│   ├── scripts
│   │   ├── benchmark_metricas.py
│   │   ├── benchmark_metricas_result.json
│   │   ├── dump_demografia.sh
│   │   ├── migrate_aliados_guiados.py
│   │   ├── restore_demografia_local.ps1
│   │   └── restore_demografia_local.sh
│   ├── tests
│   │   ├── conftest.py
│   │   ├── security
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py
│   │   │   ├── llm_stress_test.py
│   │   │   └── payloads
│   │   │       ├── cost_attack.json
│   │   │       ├── exfiltration.json
│   │   │       ├── jailbreak.json
│   │   │       └── prompt_injection.json
│   │   ├── test_afluencia_presentacion.py
│   │   ├── test_besttime.py
│   │   ├── test_competencia_busqueda.py
│   │   ├── test_ingest_shapefile_utils.py
│   │   └── test_suite.py
│   └── uv.lock
├── geo-viabilidad-data
│   ├── README.md
│   ├── geo_viabilidad_data
│   │   ├── __init__.py
│   │   ├── censo_segmentos_map.py
│   │   ├── database.py
│   │   ├── db_config.py
│   │   ├── ingest_censo_helpers.py
│   │   ├── ingest_nacional.py
│   │   ├── ingest_shapefile_utils.py
│   │   └── models.py
│   └── pyproject.toml
├── geo-viabilidad-web
│   ├── README.md
│   ├── VERSION
│   ├── app.js
│   ├── index.css
│   ├── index.html
│   └── nginx.dev.conf
├── requirements.md
├── rfc.md
├── run_local.ps1
├── run_local.sh
└── tasks.md
```
