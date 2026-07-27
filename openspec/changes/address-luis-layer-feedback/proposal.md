## Why

En el check semanal del 27-jul-2026, Luis Ramos validó la estructura por capas pero señaló confusión operativa (schemas duplicados, clients flat + v0), riesgo de acoplar desarrollo a AWS/Bedrock, falta de versionado/Commitizen para una PR grande, README insuficiente para que el equipo replique el entorno, y la necesidad de un camino de debug del análisis **sin IA** (JSON/Excel) antes de tratar el LLM como caja negra. Hay que cerrar esos huecos para que la PR de capas sea revisable y el desarrollo local no dependa de infraestructura AWS.

## What Changes

- Eliminar ambigüedad de `auth_schemas`: un solo home en `schemas/`; quitar shim en `routers/`.
- Eliminar o vaciar shims flat en `clients/*.py`; hot path solo `clients/v0/`.
- Documentar middleware real, rol de `services/assets/` y política de versionado de `report_*`.
- Reubicar `report_pdf_service` / `report_job_service` bajo `services/v0/reports/` (o documentar y versionar explícitamente como parte del contrato v0).
- Introducir abstracción de cliente LLM intercambiable (Groq/OpenAI local; Bedrock como impl opcional), sin amarrar el código a AWS.
- Añadir pre-servicio / dump de análisis cuantitativo (JSON y, si aplica, Excel) sin invocar LLM.
- Alinear `VERSION` + `pyproject.toml`; configurar Commitizen / bump SemVer para esta línea de código.
- Ampliar README API (y referencias monorepo) para que Pedro/Luis/Miguel puedan levantar, probar Swagger y correr tests.
- Preparar PR documentada con ejemplos OpenAPI/curl (demo sin front).

No hay cambios **BREAKING** de rutas HTTP de producto previstos; posibles adiciones internas (`/api/.../debug` o flag) documentadas como no-prod o protegidas.

## Capabilities

### New Capabilities

- `schema-and-client-hygiene`: Un solo catálogo de schemas; clients solo vía `v0`; assets/middleware documentados.
- `report-services-versioning`: Report PDF/job versionados bajo `services/v0/reports/` con política de compatibilidad.
- `llm-provider-abstraction`: Cliente LLM intercambiable (Adapter/Strategy); desarrollo local sin AWS/Bedrock obligatorio.
- `quantitative-debug-export`: Export/dump del pipeline cuantitativo (JSON/Excel) sin paso de IA.
- `versioning-and-runbook`: SemVer alineado + Commitizen; README runnable; checklist PR/demo Swagger.

### Modified Capabilities

- (ninguna en `openspec/specs/` main — change nuevo)

## Impact

- **Código:** `geo-viabilidad-api/app/schemas/`, `routers/`, `clients/`, `services/report_*` → `v0/reports/`, nuevo client LLM, posible endpoint/script debug, `VERSION`/`pyproject.toml`.
- **Docs:** `README.md` API, `rfcs/rfc-api-layers.md` (apéndice feedback Luis), opcional monorepo README.
- **Proceso:** PR grande con bump de versión; demo Swagger para revisión Luis/Pedro.
- **Fuera de alcance:** features de producto nuevas (tiers, pricing), split multi-repo, front SPA, Excel como producto comercial (solo debug/ops en esta fase).
