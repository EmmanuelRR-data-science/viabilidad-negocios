## Context

`geo-viabilidad-api` completó la Fase 1 de migración física a carpetas (`core/`, `routers/`, `services/`, `clients/`, `domain/`, `schemas/`), con `clients/v0/*/raw|processed` parcial y `geo-viabilidad-data` como paquete compartido. La auditoría de jul 2026 (~48/100 en pureza API) mostró routers gordos (`analytics`, `reports`), SQL/HTTP en services y domain, ciclo Bedrock→`foda_service`, clients legacy en paralelo, y ausencia de `app/exceptions/`.

Admin (~78/100 en split) ya no importa `app.*` de la API y la web está desacoplada vía nginx; faltan `clients/` y excepciones user-centric.

Este change cierra la **Fase 1.5 — pureza de fronteras**, sin split multi-repo ni features de producto.

## Goals / Non-Goals

**Goals:**

- Hacer cumplir la regla: `routers → services → (domain puro | clients)`; `clients` ↛ `services`; `domain` sin I/O.
- Introducir excepciones user-centric en API (y admin).
- Centralizar queries PostGIS/ORM en database clients.
- Unificar hot paths en `clients/v0` y documentar el árbol real.
- Mantener contratos HTTP públicos estables (rutas y payloads de éxito).

**Non-Goals:**

- Extraer repos independientes (multi-repo).
- Cambiar pricing/tiers de producto o agregar endpoints nuevos.
- Reescribir el motor analítico o el PDF desde cero.
- Migraciones de esquema PostGIS / re-ingest nacional.
- Sustituir Flask admin por otra UI.

## Decisions

### D1 — Database client como repositorio processed (no solo re-export)

- **Decisión:** Ampliar `clients/v0/database/database_client_raw.py` / `database_client_processed.py` con métodos explícitos (`obtener_demografia_ponderada`, `obtener_nse_agebs`, `resolver_categoria_google_type`, `obtener_orden_por_id`, etc.). Raw ejecuta SQL/ORM; processed tipa/normaliza a schemas.
- **Alternativa rechazada:** Introducir carpeta `infrastructure/repositories/` separada — duplicaría el rol ya asignado a `clients/v0/database` + `geo-viabilidad-data`.
- **Rationale:** Alinea con la regla org (clients raw/processed) y evita un cuarto concepto.

### D2 — Domain puro recibe DTOs, no `Session`

- **Decisión:** Refactorizar `domain/nse.py` y `domain/demografia_segmentos.py` para funciones puras sobre datos ya cargados; movers SQL a database clients. `competencia_busqueda` deja de importar Google client; el service orquesta fetch + score.
- **Alternativa rechazada:** Mantener “domain services” con Session — viola pureza y complica tests.
- **Rationale:** Tests de dominio sin DB; frontera clara.

### D3 — FODA enrichment solo en services

- **Decisión:** Bedrock processed retorna texto/estructura LLM cruda (o mínimamente parseada). `foda_service` (invocado desde report/analytics services) aplica `enriquecer_items_foda` / conclusiones.
- **Alternativa rechazada:** Mover FODA al client — mezclaría negocio en integración.
- **Rationale:** Rompe el ciclo clients→services.

### D4 — Excepciones tipadas + middleware como red de seguridad

- **Decisión:** Crear `app/exceptions/` con base `UserFacingError` y subtipos (`NotFoundError`, `PaymentRequiredError`, `ExternalDependencyError`, `ValidationUserError`). Handlers/middleware mapean a HTTP. Eliminar `HTTPException(detail=str(exc))` en rutas analytics/reports. Middleware actual permanece para no anticipados.
- **Alternativa rechazada:** Solo mejorar mensajes en middleware — no fuerza contratos en services.
- **Rationale:** Cumple guardrail user-centric SDD.

### D5 — Unificación clients v0 con shims temporales

- **Decisión:** Hot paths migran imports a `clients/v0`. Módulos flat (`google_places.py`, `bedrock.py`, …) quedan como re-exports deprecados o se vacían al final del change. MercadoPago se mueve a `clients/v0/mercadopago/`.
- **Alternativa rechazada:** Borrar flat en el primer PR sin shims — alto riesgo de imports rotos en scripts/tests.
- **Rationale:** Migración segura incremental.

### D6 — Admin: clients delgados, no reescritura total

- **Decisión:** Añadir `admin/clients/` (queries metrics/orders/leads/ingest) y `admin/exceptions/`; routes dejan de abrir `SessionLocal`. No migrar admin a FastAPI ni Pydantic obligatorio en esta fase (dataclasses/resultados existentes OK); config Pydantic queda como mejora posterior.
- **Alternativa rechazada:** Empujar todo SQL a `geo-viabilidad-data` ahora — acopla UI admin al paquete de datos demasiado pronto.
- **Rationale:** Máximo cumplimiento con mínimo alcance.

### D7 — Errores HTTP: texto puede cambiar, shape estable

- **Decisión:** Mensajes `detail` pasan a copy user-centric; no se garantiza igualdad bit-a-bit con strings previos. Status codes semánticos se preservan (404/402/403/400/502 según caso).
- **Rationale:** Mejora UX sin breaking de rutas/schemas de éxito.

## Manejo de errores orientado al usuario

| Capa | Responsabilidad |
|------|-----------------|
| clients | Capturan SDK/SQL errors, loguean, levantan `ExternalDependencyError` o retornan Result tipado |
| domain | Solo `ValidationUserError` / errores de regla de negocio puros |
| services | Traducen fallos de orquestación a excepciones tipadas |
| routers | No atrapan con `str(exc)`; dejan propagar o mapean excepciones tipadas a response |
| middleware | Última red para OperationalError/Boto/RequestException → mensaje empático |

## Risks / Trade-offs

- **[Riesgo] Diff grande en `analytics_service` / reports** → Mitigación: migrar por vertical (analytics routers → SQL demografía/NSE → FODA → clients legacy → admin).
- **[Riesgo] Tests frágiles acoplados a SQL en domain** → Mitigación: actualizar tests a fixtures de dicts; mocks solo en client layer.
- **[Riesgo] Shims legacy olvidados** → Mitigación: tarea final de grep + fallar CI si hot paths importan flat (opcional script/check).
- **[Trade-off] Admin sin Pydantic BaseSettings aún** → Aceptado para no mezclar refactor de config.
- **[Trade-off] Mensajes de error cambian** → Documentar en changelog interno; front ya muestra `detail` genérico.

## Migration Plan

1. Introducir `app/exceptions/` + tests de mapeo (sin cambiar callers masivos).
2. Extender database clients; redirigir demografía/NSE/categorías; purificar domain.
3. Adelgazar routers analytics/reports.
4. Romper Bedrock↔FODA; migrar S3/SES paths a clients.
5. Migrar hot-path imports a v0; shims; MercadoPago v0.
6. Admin clients + exceptions + routes sin SessionLocal.
7. Actualizar docs; grep de verificación; suite de tests.

**Rollback:** Revert del PR/branch; sin migraciones de BD, rollback es de código únicamente.

## Open Questions

1. ¿Incluir check automatizado (test o lint custom) que falle si `routers` importan `clients`/`domain` (excepto `get_db`)? — Recomendación: sí, test de arquitectura liviano.
2. ¿SES email debe vivir en `clients/v0/ses/` nuevo o bajo un client `notifications`? — Default propuesto: `clients/v0/ses/` raw/processed mínimo.
3. ¿Mover schemas de `routers/auth_schemas.py` a `schemas/` en este change? — Default: sí, como tarea menor acoplada a auth service (evita service→router import).
