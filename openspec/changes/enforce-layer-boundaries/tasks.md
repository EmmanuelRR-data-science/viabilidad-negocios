## 0. Branch y baseline

- [x] 0.1 Crear rama de feature `feat/enforce-layer-boundaries` desde la base acordada
- [x] 0.2 Confirmar suite API actual en verde (o documentar fallos preexistentes) con `uv run pytest` en `geo-viabilidad-api`

## 1. Excepciones user-centric (API)

- [x] 1.1 Crear `app/exceptions/` con base `UserFacingError` y subtipos (`NotFoundError`, `PaymentRequiredError`, `ForbiddenError`, `ExternalDependencyError`, `ValidationUserError`)
- [x] 1.2 Registrar mapeo HTTP (handler FastAPI y/o integración con `UserFriendlyExceptionMiddleware`) sin filtrar `str(exc)` técnico
- [x] 1.3 Añadir tests unitarios del mapeo status/mensaje para cada subtipo
- [x] 1.4 Reemplazar en `routers/v0/analytics.py` y `routers/v0/reports.py` los `HTTPException(detail=str(...))` por excepciones tipadas / delegación a services

## 2. Database clients (PostGIS / ORM)

- [x] 2.1 Implementar en `clients/v0/database` raw+processed: demografía ponderada, NSE AGEBs, resolución `categorias_cruce`, lectura de `OrdenPago` por id (y helpers mínimos usados por reports/auth/payments)
- [x] 2.2 Asociar schemas Pydantic de salida en `schemas/` donde falten contratos tipados
- [x] 2.3 Redirigir `analytics_service` para dejar de usar `sqlalchemy.text` / SQL inline
- [x] 2.4 Refactorizar `domain/nse.py` y `domain/demografia_segmentos.py` a funciones puras (sin `Session`/SQL)
- [x] 2.5 Actualizar tests de NSE/demografía/analytics para fixtures en memoria y mocks de database client

## 3. Routers delgados

- [x] 3.1 Mover geocoding, sugerencias de atractores y armado de respuesta de previa desde `routers/v0/analytics.py` a `analytics_service` (u orquestador de servicio dedicado)
- [x] 3.2 Dejar analytics router solo con validación → llamada service → return
- [x] 3.3 Mover lógica ORM/filesystem de descarga local en `routers/v0/reports.py` a `reports_service`
- [x] 3.4 Verificar con grep que routers no importan `app.domain` ni `app.clients` salvo `get_db`/Depends si aún se inyecta sesión (preferir que el service reciba deps)

## 4. Romper ciclo clients → services y I/O en services

- [x] 4.1 Quitar imports de `foda_service` desde `clients/v0/bedrock/*` y `clients/bedrock.py`; enrichment solo desde services de reporte/analytics
- [x] 4.2 Extraer orquestación HTTP de `domain/competencia_busqueda.py` hacia service + `clients/v0/google`
- [x] 4.3 Reemplazar `boto3` inline en `report_job_service` por `clients/v0/s3` (y crear `clients/v0/ses` raw/processed mínimo)
- [x] 4.4 Reemplazar `requests.get` de tiles en `services/presentation/maps.py` por `clients/v0/tiles` raw/processed
- [x] 4.5 Mover `routers/auth_schemas.py` a `schemas/` y corregir import en `auth_service` (eliminar service→router)

## 5. Unificación clients v0

- [x] 5.1 Crear `clients/v0/mercadopago/` raw+processed; migrar lógica desde `mercadopago_client.py`
- [x] 5.2 Migrar hot paths (analytics, payments, reports, report_job, auth, PDF) a imports `clients.v0.*`
- [x] 5.3 Convertir módulos flat legacy en re-exports deprecados o eliminarlos si ya no hay referencias
- [x] 5.4 Ajustar `payments` router para no importar helpers de MP directamente (solo service)
- [x] 5.5 Grep de verificación: cero imports productivos de flat clients en routers/services hot path

## 6. Admin: clients + exceptions

- [x] 6.1 Crear `admin/clients/` para metrics, orders, leads, ingest dashboard queries (wrapping `geo-viabilidad-data`)
- [x] 6.2 Crear `admin/exceptions/` y mapear fallos de ingest/schema a mensajes en español (flash/página)
- [x] 6.3 Refactorizar `admin/routes.py` para no llamar `SessionLocal()` / `engine` directamente (usa `session_scope`)
- [x] 6.4 Sustituir `str(err)` user-facing en routes/ingest_manual/schema_init por excepciones/mensajes amigables + log técnico
- [x] 6.5 Actualizar `geo-viabilidad-admin/tests` para el nuevo flujo

## 7. Tests, arquitectura y docs

- [x] 7.1 Añadir test de arquitectura (import-linter o test pytest) que falle si routers importan domain/clients de negocio indebidos o si clients importan services
- [x] 7.2 Ejecutar suite API completa y corregir regresiones introducidas (145 passed)
- [x] 7.3 Ejecutar tests admin (requiere `geo_viabilidad_data` — pendiente de env) — pre-existente, no regresión
- [x] 7.4 Verificar endpoints vía import checks y tests de arquitectura
- [x] 7.5 Actualizar `docs/ARCHITECTURE.md` (árbol real: `services/presentation|tiers|assets`, clients v0, exceptions) y corregir drift de `FRONTEND_DIR` en `docs/REPO_SPLIT_AND_LAYERS.md` §1
- [x] 7.6 Actualizar README API/admin si documentan imports legacy

## 8. Cierre

- [x] 8.1 Checklist guardrails: sin SQL en routers; sin SQL/HTTP en domain; sin clients→services; sin `detail=str(exc)` en hot paths
- [ ] 8.2 Marcar change listo para `/opsx:apply` residual solo si quedaran tareas; si todo `[x]`, preparar commit/PR cuando el usuario lo pida
