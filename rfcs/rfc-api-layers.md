Author(s): Emmanuel Ramírez Romero · revisión Pedro Hernández · Luis Ramos
Status: Aceptado / implementado (Fase 1 + Fase 1.5 pureza de fronteras)
Ultima actualización: 2026-07-24

---

# RFC: Capas de la API (rfc-api-layers)

## Objetivo

Formalizar el diseño por capas y la separación de responsabilidades dentro de **geo-viabilidad-api**. Este RFC es **técnico** (refactor de fronteras), no de negocio: no define reglas comerciales nuevas; documenta cómo organizar el código para que routers, servicios, dominio, clientes, esquemas y excepciones tengan responsabilidades claras y dependencias unidireccionales.

**Estado (24-jul-2026):**

| Fase | Alcance | Estado |
|------|---------|--------|
| **Fase 1** | Migración física a carpetas (`core/`, `routers/`, `services/`, `clients/`, `domain/`, `schemas/`); presentation/tiers/assets dentro de `services/`; BD en `clients/v0/database/` | **Hecha** |
| **Fase 1.5** | Pureza de fronteras: routers delgados, domain sin I/O, SQL en database clients, ciclo clients↛services roto, `app/exceptions/`, unificación hot paths en `clients/v0`, admin con `clients/` + `exceptions/` | **Hecha** (`openspec/changes/enforce-layer-boundaries`) |

---

## Goals

* Separar responsabilidades del backend en capas con regla de dependencia unidireccional.
* Mantener routers delgados: validar entrada, autenticar, delegar; sin lógica de negocio, sin ORM/SQL y sin llamar `domain`/`clients` de negocio (salvo `get_db` para DI).
* Concentrar orquestación y reglas de negocio en `services/` (incluye PDF/`presentation`, FODA, estrategias por tier).
* Aislar reglas puras (SVA, NSE, competencia keywords/merge, aliados) en `domain/` **sin SQL, sin HTTP, sin `Session`**.
* Exponer integraciones externas solo vía `clients/v0/*/raw|processed` (APIs + PostGIS + SES + tiles).
* Mantener contratos Pydantic/TypedDict en `schemas/` como capa transversal (`auth_schemas` vive en `schemas/`, no en routers).
* Versionar implementaciones bajo `services/v0/` / `clients/v0/` sin romper URLs canónicas.
* Resolver capacidades por tier en el servidor (`services/tiers/{basico,pro,premium}`) usando la orden de pago como fuente de verdad.
* Manejar errores de forma user-centric vía `app/exceptions/` + handler FastAPI + middleware como red de seguridad; logs técnicos solo en servidor.
* Conservar equivalencia funcional: suite de tests en verde; tests de arquitectura (`tests/test_architecture_layers.py`) como gate de fronteras.
* Documentar scripts operativos (ingesta INEGI, demografía) como CLIs de servidor, no como API pública.
* Unificar scripts de operación a shell (`.sh`) ejecutables vía WSL en Windows.

---

## Non-Goals

* Orquestar Docker, balanceadores, aprovisionamiento de BD física o hardening de VPS.
* Incluir scripts de VPS (`vps-hardening*`, `vps-recover*`, `vps-ufw*`) en este repositorio.
* Split multi-repo de web/admin/api (ver `docs/REPO_SPLIT_AND_LAYERS.md`; fuera del alcance de pureza).
* Añadir o quitar funcionalidades de negocio del backend (solo reubicar y clarificar lo existente).
* Cambiar contratos HTTP públicos de forma incompatible (mismas rutas `/api/*`; los **textos** de error pueden volverse más amigables).
* Mezclar contexto de negocio del RFC de producto con este RFC técnico.
* Mantener dualidad PowerShell (`.ps1`) + Shell para la misma operación.
* Migrar admin a FastAPI o imponer Pydantic BaseSettings en admin en esta fase.

---

## Background

El backend operaba con ~35 archivos planos en `app/` mezclando HTTP, orquestación, dominio, clientes externos y renderizado PDF. Se migró a capas (Fase 1). En la revisión del 20-jul-2026, Pedro y Luis acordaron:

1. **Presentation no es capa** → módulo dentro de `services/`.
2. **Infrastructure (BD) no es capa** → cliente dentro de `clients/`.
3. **Schemas** permanecen transversales.
4. **Tiers** se diferencian con estrategias en servicios; el tier efectivo no se confía al request del cliente.
5. **Scripts VPS** salen del repo API; scripts de ingesta viven como CLI.
6. **Goals/Non-Goals** atómicos; métrica de tests como gate de equivalencia.

La auditoría de jul-2026 (~48/100 en pureza API) mostró que las carpetas existían pero las fronteras aún se violaban: routers gordos, SQL en domain/services, ciclo Bedrock→`foda_service`, clients flat en paralelo, sin `app/exceptions/`. El change OpenSpec **`enforce-layer-boundaries`** cerró esa **Fase 1.5**.

---

## Overview — regla de dependencias

```mermaid
flowchart TD
    subgraph core [core — transversal]
        Config[config]
        MW[middleware]
        Sec[security]
    end

    subgraph exceptions [exceptions — user-centric]
        UFE[UserFacingError + subtipos]
    end

    Request[Petición HTTP] --> Routers[routers/]
    Routers --> Services[services/]
    Services --> Domain[domain/]
    Services --> Clients[clients/v0]
    Services --> SchemasAPI[schemas/]
    Services --> UFE
    Clients --> UFE
    Routers -.->|handler| UFE

    subgraph services_mod [módulos de services]
        Tiers[tiers/basico|pro|premium]
        Presentation[presentation/ + assets/]
        Orch[analytics · payments · reports · PDF · FODA]
    end
    Services --- services_mod

    subgraph clients_mod [clients/v0 — fuentes externas]
        Ext[Google · MP · Bedrock · BestTime · S3 · SES · tiles]
        Db[(database raw + processed)]
    end
    Clients --- clients_mod

    Domain --> SchemasDomain[schemas/domain/]
    Routers --> SchemasAPI
    Clients --> SchemasAPI

    core --> Routers
    core --> Services
    core --> Clients
    MW --> Request
```

| Capa / módulo | Puede importar de | No debe importar de |
|---------------|-------------------|---------------------|
| `routers/` | `services`, `schemas`, `core.security`, `core.config`, `exceptions`, `clients` **solo** `get_db` (DI) | `domain`, clients de negocio, ORM/`db.query`, armado de respuesta de negocio |
| `services/` | `domain`, `clients`, `schemas`, `core`, `exceptions`, `services.presentation`, `services.tiers` | `routers` |
| `services/presentation/` | datos ya calculados, `clients/v0/tiles` para fetch de mapa | `routers`, SQL de negocio |
| `services/tiers/` | `registry` + strategies; datos de orden/pago | confiar en `tier_id` del body sin validar orden |
| `domain/` | `schemas/domain`, funciones puras entre sí | `routers`, `clients`, SQL, HTTP, `Session` |
| `clients/` | `schemas`, `core.config`, `exceptions`, SDKs / `geo_viabilidad_data` | `routers`, **`services`** (ciclo prohibido) |
| `exceptions/` | stdlib | capas de negocio (salvo tipado) |
| `schemas/` | Pydantic, validadores de dominio | capas superiores (salvo casos puntuales) |
| `core/` | stdlib, FastAPI (solo en `security`), `exceptions` en middleware | `services`, `domain` |

### Decisión: cliente de base de datos (Raw + Processed)

Pedro definió cliente como el programa que comunica servicios con **fuentes externas**. La BD PostGIS entra en esa definición.

| Opción | Pros | Contras |
|--------|------|---------|
| **A. Raw + Processed** (`clients/v0/database/`) | Misma forma que Google/Bedrock/S3; Raw = SQL/sesión; Processed = tipado/normalizado | Más archivos |
| **B. Re-export delgado** (ex-`infrastructure/`) | Mínimo código | Rompe simetría; “capa especial” |

**Decisión:** **Opción A**. `geo-viabilidad-data` es dueño del ORM/ingesta; la API expone el puente y las queries espaciales (demografía, NSE, `categorias_cruce`, órdenes) en `clients/v0/database/`. Domain recibe agregados ya cargados (`construir_nse_desde_raw`, etc.).

### Decisión: FODA enrichment en services (no en clients)

Bedrock processed expone invocación LLM cruda (`invocar_foda_llm_raw`). El enrichment narrativo (`enriquecer_lista_lectura`, conclusiones) vive en `services/foda_service.py` + `services/presentation/narrative.py`. **Clients no importan `app.services`.**

### Decisión: excepciones tipadas

`app/exceptions/`:

| Tipo | Status típico |
|------|---------------|
| `UserFacingError` | base |
| `NotFoundError` | 404 |
| `PaymentRequiredError` | 402 |
| `ForbiddenError` | 403 |
| `ExternalDependencyError` | 502 (o 503 config) |
| `ValidationUserError` | 400 |

Handler en `main.py` + `UserFriendlyExceptionMiddleware` como red de seguridad. No filtrar `detail=str(exc)` técnico al cliente.

### Decisión: tiers como estrategias en services

```
services/tiers/
├── definitions.json
├── registry.py
├── basico.py
├── pro.py
└── premium.py
```

Flujo de autoridad (Luis — anti-manipulación):

```
Front envía intención de compra (tier_id)
        → Router autentica usuario
        → payment_service crea orden con monto del registry (servidor)
        → Mercado Pago webhook confirma pago
        → OrdenPago en BD = fuente de verdad del tier
        → report_job usa get_tier_strategy(orden.tier_adquirido)
        → Strategy decide APIs / secciones PDF
```

---

## Árbol de directorios — `geo-viabilidad-api/`

Estado real post Fase 1.5 (24-jul-2026). Omite `.venv/`, cachés y scratch.

```
geo-viabilidad-api/
│
├── VERSION
├── Dockerfile
├── pyproject.toml
├── pyproject.toml / uv.lock              # Dependencias con uv (+ Ruff/Commitizen)
├── uv.lock
├── README.md
│
├── app/
│   ├── main.py                      ← Wiring + handler UserFacingError + /health
│   │
│   ├── core/                        ← config, middleware, security
│   │   ├── config.py
│   │   ├── middleware.py
│   │   └── security.py
│   │
│   ├── exceptions/                  ← UserFacingError + subtipos
│   │   ├── __init__.py
│   │   └── base.py
│   │
│   ├── routers/                     ← HTTP delgado
│   │   ├── auth.py
│   │   ├── auth_schemas.py          ← shim → schemas/auth_schemas.py
│   │   └── v0/
│   │       ├── analytics.py
│   │       ├── payments.py
│   │       └── reports.py
│   │
│   ├── services/                    ← Orquestación + módulos de negocio
│   │   ├── auth_service.py
│   │   ├── aliados_guiados_service.py
│   │   ├── foda_service.py          ← Orquesta Bedrock raw + narrative
│   │   ├── report_pdf_service.py
│   │   ├── report_job_service.py    ← Usa clients/v0/s3 + ses
│   │   ├── presentation/            ← afluencia, charts, maps, narrative
│   │   ├── assets/
│   │   ├── tiers/
│   │   │   ├── definitions.json
│   │   │   ├── registry.py
│   │   │   ├── basico.py
│   │   │   ├── pro.py
│   │   │   └── premium.py
│   │   └── v0/
│   │       ├── analytics/analytics_service.py
│   │       ├── payments/payment_service.py
│   │       └── reports/reports_service.py
│   │
│   ├── domain/                      ← Reglas puras (sin I/O)
│   │   ├── sva_calculo.py
│   │   ├── nse.py
│   │   ├── demografia_segmentos.py
│   │   ├── competencia_busqueda.py  ← keywords/merge; HTTP en service
│   │   ├── aliados_deterministico.py
│   │   ├── aliados_guiados.py
│   │   ├── seleccion_atractores.py
│   │   └── vigencia_comercio.py
│   │
│   ├── clients/
│   │   ├── google_auth.py           ← shim / legacy
│   │   ├── google_places.py         ← shim / legacy
│   │   ├── besttime.py              ← shim / legacy
│   │   ├── bedrock.py               ← shim → v0 (sin importar services)
│   │   ├── mercadopago_client.py    ← shim → v0/mercadopago
│   │   └── v0/
│   │       ├── bedrock/      (raw + processed; LLM crudo)
│   │       ├── besttime/     (raw + processed)
│   │       ├── google/       (raw + processed)
│   │       ├── mercadopago/  (raw + processed)
│   │       ├── s3/           (raw + processed)
│   │       ├── ses/          (raw + processed)
│   │       ├── tiles/        (raw + processed; mapas PDF)
│   │       └── database/     (raw = SQL/sesión; processed = tipado)
│   │
│   └── schemas/                     ← Contratos transversales
│       ├── auth_schemas.py
│       ├── domain/
│       └── v0/
│
├── scripts/
│   ├── README.md
│   ├── ingest_inegi/
│   ├── demografia/
│   ├── benchmark_metricas.py
│   └── migrate_aliados_guiados.py
│
└── tests/
    ├── test_architecture_layers.py  ← Gate de fronteras (AST)
    ├── test_exceptions.py
    └── …
```

### Lectura rápida para el revisor

| Ubicación | ¿Capa? | Nota |
|-----------|--------|------|
| `app/core/` | Transversal | Config / middleware / auth dependency |
| `app/exceptions/` | Transversal | Errores user-centric |
| `app/routers/` | Sí | Entrada HTTP delgada |
| `app/services/` | Sí | Orquestación; `presentation/`, `assets/`, `tiers/`, `foda_service` |
| `app/domain/` | Sí | Pura (sin I/O) |
| `app/clients/` | Sí | APIs + database + SES + tiles; hot path = `v0/` |
| `app/schemas/` | Transversal | Data contracts |
| `scripts/` | Operación | CLI; no endpoints |

### Admin (alcance relacionado)

`geo-viabilidad-admin` aplica el mismo espíritu (sin ser el foco del RFC API):

* `admin/clients/` — `session_scope`, `get_engine`, queries de métricas
* `admin/exceptions/` — mensajes amigables al operador
* `admin/routes.py` — sin `SessionLocal()` / `engine` directos

---

## Detailed Design

### 1. Core (`app/core/`)

Config, middleware user-centric (infra no anticipada), `get_current_user`. Rate-limit LLM en rutas sensibles.

### 2. Exceptions (`app/exceptions/`)

Catálogo tipado + `@app.exception_handler(UserFacingError)` en `main.py`. Middleware atrapa `OperationalError` / boto / `RequestException` no convertidos.

### 3. Routers (`app/routers/`)

HTTP delgado. Prefijos: `/api/auth`, `/api/pagos`, `/api/analizar`, `/api/reportes`. Health en `GET /health` (wiring en `main.py`).

Ejemplo de delgadez: `POST /api/analizar/previa` solo parsea body → `obtener_vista_previa_service(...)` → return.

### 4. Services (`app/services/`)

| Módulo | Responsabilidad |
|--------|-----------------|
| `v0/payments/` | Órdenes, preferencias MP, webhooks, máquina de estados |
| `v0/analytics/` | Motor analítico; orquesta DB client + domain + Google; competencia HTTP |
| `v0/reports/` | Descarga PDF post-pago; path local |
| `foda_service.py` | LLM raw + enrichment narrativo |
| `report_pdf_service.py` | Ensambla PDF; `presentation/` + `assets/` |
| `report_job_service.py` | Job async; S3/SES vía clients |
| `presentation/` | Gráficas, mapas (tiles client), afluencia, narrativa |
| `tiers/` | Registry + strategies |

### 5. Domain (`app/domain/`)

SVA, NSE (desde raw), demografía (desde raw), keywords/merge de competencia, aliados, vigencia. **Sin `sqlalchemy`, sin `app.clients`.**

### 6. Clients (`app/clients/`)

Integraciones Raw + Processed bajo `clients/v0/`.

Proveedores: Google, BestTime, Bedrock/Groq, Mercado Pago, S3, SES, tiles, **database (PostGIS)**.

Módulos flat en `clients/*.py` = shims de re-export; hot paths importan `clients.v0.*`.

### 7. Schemas (`app/schemas/`)

`v0/` = contratos HTTP y DTOs de proveedores; `domain/` = TypedDicts internos; `auth_schemas.py` canónico (shim en routers).

### 8. Scripts

- CLIs documentados (`ingest_inegi/`, `demografia/`).
- Solo `.sh` (+ Python); Windows vía **WSL**.
- Scripts VPS **fuera** de este repo.

---

## Spike de moves — checklist histórico

### Fase 1 (21-jul-2026)

- [x] `app/presentation/` → `app/services/presentation/`
- [x] `app/assets/` → `app/services/assets/`
- [x] `app/infrastructure/` → `app/clients/v0/database/`
- [x] `app/tiers/` → `app/services/tiers/` + strategies
- [x] Eliminar `scripts/vps-*.sh` del repo API
- [x] Agrupar scripts INEGI/demografía + `scripts/README.md`
- [x] Cablear `get_tier_strategy` en report/analytics/payments
- [x] Ruff limpio; equivalencia (~79 passed en ese momento)

### Fase 1.5 (24-jul-2026) — `enforce-layer-boundaries`

- [x] `app/exceptions/` + handler + tests
- [x] SQL demografía/NSE/categorías/órdenes → `clients/v0/database`
- [x] Domain NSE/demografía/competencia sin I/O
- [x] Routers analytics/reports delgados
- [x] Romper Bedrock → services; FODA en `foda_service`
- [x] `clients/v0/{ses,tiles,mercadopago}/`
- [x] Hot paths sin boto3/`requests` inline en services de job/maps
- [x] `schemas/auth_schemas.py`; shim en routers
- [x] Admin `clients/` + `exceptions/` + routes sin `SessionLocal`
- [x] `tests/test_architecture_layers.py` + `test_exceptions.py`
- [x] Docs `ARCHITECTURE.md` / drift `FRONTEND_DIR` en `REPO_SPLIT_AND_LAYERS.md`

---

## Consideraciones

### Seguridad de tiers (Luis)

* No confiar en `tier_id` del body para desbloquear features.
* Auth + orden pagada definen entitlement.
* Webhook idempotente; contemplar timeout MP; doble clic / refresh.

### Equivalencia y fronteras (Pedro + Fase 1.5)

* Gate equivalencia: suite API en verde (`uv run pytest tests/ --ignore=tests/security`).
* Gate fronteras: AST tests — routers ↛ domain; clients/v0 ↛ services; domain ↛ sqlalchemy/clients.
* No añadir features de producto en este RFC.

### Residuos aceptados (corto plazo)

* Shims flat en `clients/*.py` (re-export a v0).
* Algunos `HTTPException` legacy aún en `payment_service` / auth (migración gradual a `UserFacingError`).
* Health en `GET /health` (no bajo prefijo `/api`); documentado en tests.

---

## Criterios de aceptación

### Fase 1

- [x] Raíz de `app/` solo `main.py` (+ paquetes de capa)
- [x] Sin `presentation/` ni `infrastructure/` en raíz de `app/`
- [x] BD bajo `clients/v0/database/`
- [x] Tiers bajo `services/tiers/` con strategies cableadas
- [x] Sin scripts `vps-*` en el repo API
- [x] Scripts documentados; solo shell (+ WSL)

### Fase 1.5

- [x] Existe `app/exceptions/` con handler user-centric
- [x] Domain sin SQL/HTTP/`Session`
- [x] Clients no importan `app.services`
- [x] Routers analytics/reports sin `domain` ni clients de negocio (salvo `get_db`)
- [x] Database queries espaciales en `clients/v0/database`
- [x] MercadoPago / SES / tiles bajo `clients/v0/`
- [x] Tests de arquitectura en verde
- [x] Suite equivalencia: **145 passed** (`--ignore=tests/security`)

---

## Métricas

| Métrica | Antes (plano) | Tras Fase 1 | Tras Fase 1.5 (24-jul-2026) |
|---------|---------------|-------------|------------------------------|
| Capas “extra” fuera del modelo | N/A | 0 (presentation/infra absorbidos) | 0 + `exceptions/` transversal |
| Pureza de fronteras | N/A | Parcial (~48/100 auditoría) | Enforceada (AST + refactor) |
| Estrategias de tier | 0 | basico/pro/premium | Sin cambio (ya cableadas) |
| Clients v0 | Parcial | Google/Bedrock/BestTime/S3/DB | + MercadoPago, SES, tiles |
| Scripts VPS en repo API | sí | 0 | 0 |
| Tests equivalencia (sin security) | suite | ~79 passed | **145 passed** |

### Desempeño (baseline producto — ver `rfc-geo-viabilidad-api.md`)

Medición 2026-06-19 vía `scripts/benchmark_metricas.py` (VPS). Resumen:

| Flujo | Tiempo |
|-------|--------|
| PostGIS demografía / NSE | 61 ms / 26 ms |
| Vista previa (`/api/analizar/previa`) | ~4.7 s |
| Preferencia de pago | ~212 ms |
| Primer resultado post-pago | ~4.3 s |
| PDF listo (poll Básico) | ~2.9 s |
| Resultado con caché | ~428 ms |

---

## Apéndice — Feedback Luis (27-jul-2026) → follow-up

Check semanal EDM. Luis validó la estructura y pidió:

1. Un solo home de schemas (sin `routers/auth_schemas` paralelo)
2. Un solo árbol de clients (`v0`; sin dual flat/legacy confuso)
3. No amarrar desarrollo a AWS/Bedrock → `LLM_PROVIDER` intercambiable
4. Versionar `report_pdf` / `report_job` bajo `services/v0/reports/`
5. Dump cuantitativo **JSON + Excel** sin IA para solidificar el payload
6. SemVer **1.0.0** alineado + README runnable + PR/demo Swagger

**Change OpenSpec:** `openspec/changes/address-luis-layer-feedback/`  
**Decisiones de aprobación:** Excel en el change; env `LLM_PROVIDER`; SemVer `1.0.0`.

### Implementación (branch `feat/address-luis-layer-feedback`)

- [x] `routers/auth_schemas.py` eliminado; single home `schemas/auth_schemas.py`
- [x] Clients hot-path migrados a `clients/v0/` (google_giro_filter, google_auth, besttime, bedrock)
- [x] Shims flat reducidos a re-exports deprecados (solo para compat tests/security)
- [x] `report_pdf_service` y `report_job_service` bajo `services/v0/reports/`
- [x] Facade LLM en `clients/v0/llm/` con adapters groq/openai/bedrock + `LLM_PROVIDER` env
- [x] Debug cuantitativo: script CLI `scripts/debug_analisis_cuantitativo.py` (JSON + Excel) + endpoint DEV_MODE
- [x] SemVer 1.0.0 alineado; Commitizen config en `pyproject.toml`
- [x] README actualizado con: LLM_PROVIDER, debug dump, compose/run_local, middleware real, assets

---

## Links

- Change OpenSpec Fase 1.5: `openspec/changes/enforce-layer-boundaries/`
- Change OpenSpec feedback Luis: `openspec/changes/address-luis-layer-feedback/`
- Plan multi-repo: `docs/REPO_SPLIT_AND_LAYERS.md`
- Arquitectura monorepo: `docs/ARCHITECTURE.md`
- RFC API producto: `rfcs/rfc-geo-viabilidad-api.md`
- RFC paquete data: `rfcs/rfc-geo-viabilidad-data.md`
- Transcripción revisión 20-jul-2026: comentarios Pedro Hernández / Luis Ramos
- Check 27-jul-2026: feedback estructura (Luis Ramos)