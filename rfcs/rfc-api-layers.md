Author(s): Emmanuel Ramírez Romero · revisión Pedro Hernández · Luis Ramos
Status: Aceptado / implementado (Fase 1 + Fase 1.5 + feedback Luis + auth/sesión + shims eliminados)
Ultima actualización: 2026-07-29

---

# RFC: Capas de la API (rfc-api-layers)

## Objetivo

Formalizar el diseño por capas y la separación de responsabilidades dentro de **geo-viabilidad-api**. Este RFC es **técnico** (refactor de fronteras), no de negocio: no define reglas comerciales nuevas; documenta cómo organizar el código para que routers, servicios, dominio, clientes, esquemas y excepciones tengan responsabilidades claras y dependencias unidireccionales.

**Estado (29-jul-2026):**

| Fase | Alcance | Estado |
|------|---------|--------|
| **Fase 1** | Migración física a carpetas (`core/`, `routers/`, `services/`, `clients/`, `domain/`, `schemas/`); presentation/tiers/assets dentro de `services/`; BD en `clients/v0/database/` | **Hecha** |
| **Fase 1.5** | Pureza de fronteras: routers delgados, domain sin I/O, SQL en database clients, ciclo clients↛services roto, `app/exceptions/`, unificación hot paths en `clients/v0`, admin con `clients/` + `exceptions/` | **Hecha** (`openspec/changes/enforce-layer-boundaries`) |
| **Feedback Luis** | Schemas únicos, clients hot-path solo `v0/`, LLM intercambiable, PDF/job bajo `services/v0/reports/`, SemVer 1.0.0 | **Hecha** (`openspec/changes/address-luis-layer-feedback`) |
| **Auth / superficie HTTP** | Sesión de app (`gv_session`), mock auth solo en `DEV_MODE`, mapa público acotado, PDF con token one-time, webhook MP firmado, CORS allowlist | **Hecha** (jul-2026; checklist en `docs/SECURITY_CHECKLIST.md`) |
| **Limpieza shims** | Eliminados re-exports DEPRECATED flat (`clients/*.py`, `services/report_*`); hot path solo `v0/`; gate AST | **Hecha** (29-jul-2026) |

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
* Mantener la **superficie HTTP** alineada a las capas: auth en `core/` + `auth_service`; routers delgados; únicos endpoints públicos intencionales documentados (mapa + health + config auth/pagos).
* Separar flags de entorno con responsabilidades distintas (`DEV_MODE` ≠ `PAYMENTS_MOCK` ≠ `MERCADOPAGO_SANDBOX`).

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
* Eliminar del repo el código de mock de pagos/auth: se **desactiva por flags** en producción; no es requisito borrar el código para endurecer.

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
        Sec[security + session/download tokens]
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
        Orch[analytics · payments · v0/reports · FODA · auth]
    end
    Services --- services_mod

    subgraph clients_mod [clients/v0 — fuentes externas]
        Ext[Google · MP · LLM · BestTime · S3 · SES · tiles]
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
| `core/` | stdlib, FastAPI (solo en `security` / tokens), `exceptions` en middleware | `services`, `domain` |

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

### Decisión: sesión de aplicación (no ID token Google en hot path)

```
POST /api/auth/google  (credential = ID token Google, una vez)
        → auth_service valida con clients/v0/google/google_auth
        → core/session_tokens emite JWT de app (jti, roles, TTL)
        → Cookie HttpOnly gv_session (+ Bearer solo Swagger/DEV)
        → get_current_user (core/security) acepta sesión de app
        → ID token de Google rechazado en endpoints de negocio
```

* Tokens mock (`mock-token`, `mock-jwt-user`, `mock-jwt-admin`) **solo si `DEV_MODE=true`**. Con `DEV_MODE=false` → 401.
* Logout revoca `jti` (`session_tokens`) y limpia cookie.
* **No** aceptar Bearer arbitrarios en DEV: solo mock allowlist o JWT de sesión válido (evita bypass con basura/`alg:none`).

### Decisión: flags de entorno independientes

| Flag | Responsabilidad | No confundir con |
|------|-----------------|------------------|
| `DEV_MODE` | Entorno app: AWS off, Groq default, `/docs`, debug cuantitativo, **mock auth**, CORS localhost, secretos | Pagos |
| `PAYMENTS_MOCK` | Checkout simulado vs Mercado Pago real; registra `webhook-mock` solo si true | `DEV_MODE` |
| `MERCADOPAGO_SANDBOX` | Sandbox vs live de MP (cuando `PAYMENTS_MOCK=false`) | Mock de app |
| `REPORTS_LOCAL_STORAGE` | PDF en disco local vs S3 | `DEV_MODE` |

Ejemplo válido: `DEV_MODE=true` + `PAYMENTS_MOCK=false` + sandbox → demo con Checkout Pro sin “modo producción”.

### Decisión: superficie pública acotada (mapa)

Únicos endpoints de negocio **sin** `get_current_user` (además de health / configs públicas):

| Ruta | Motivo | Mitigación |
|------|--------|------------|
| `GET /api/analizar/geocodificar` | Mapa antes del login (reverse geocode) | Rate limit por IP (`AbuseRateLimitMiddleware`) |
| `GET /api/analizar/buscar-direccion` | Buscador del mapa | Idem |

`POST /api/analizar/previa`, resultados, pagos, PDF meta y debug cuantitativo **requieren auth**. Descarga binaria del PDF: `GET .../descargar?token=` firmado one-time (`core/download_tokens`), sin montar `/static/reports`.

### Decisión: assets PDF canónicos en `services/assets/`

Tras mover `report_pdf_service` a `services/v0/reports/`, las imágenes de portada/logo siguen en **`app/services/assets/`** (no junto al módulo PDF). El generador resuelve `_ASSETS_DIR` relativo a `services/assets/`. Rutas incorrectas dejan la portada en relleno oscuro `#212121` sin el diseño Fibonacci.

---

## Árbol de directorios — `geo-viabilidad-api/`

Estado real post feedback Luis + auth (29-jul-2026). Omite `.venv/`, cachés y scratch.

```
geo-viabilidad-api/
│
├── VERSION
├── Dockerfile
├── pyproject.toml                    # uv + Ruff + Commitizen
├── uv.lock
├── README.md
│
├── app/
│   ├── main.py                      ← Wiring + handler UserFacingError + /health
│   │                                  (docs/OpenAPI solo si DEV_MODE; sin /static/reports)
│   │
│   ├── core/                        ← config, middleware, security, tokens
│   │   ├── config.py                ← DEV_MODE, PAYMENTS_MOCK, SESSION_*, CORS, LLM_PROVIDER
│   │   ├── middleware.py            ← LLM + abuse rate limits (geo público)
│   │   ├── security.py              ← get_current_user (sesión; mock solo DEV)
│   │   ├── session_tokens.py        ← JWT app + revoke jti
│   │   └── download_tokens.py       ← token PDF one-time
│   │
│   ├── exceptions/                  ← UserFacingError + subtipos
│   │   ├── __init__.py
│   │   └── base.py
│   │
│   ├── routers/                     ← HTTP delgado
│   │   ├── auth.py
│   │   └── v0/
│   │       ├── analytics.py         ← geo público; resto con auth
│   │       ├── payments.py
│   │       └── reports.py           ← meta auth; descargar ?token=
│   │
│   ├── services/                    ← Orquestación + módulos de negocio
│   │   ├── auth_service.py
│   │   ├── aliados_guiados_service.py
│   │   ├── foda_service.py          ← Orquesta LLM facade + narrative
│   │   ├── presentation/            ← afluencia, charts, maps, narrative
│   │   ├── assets/                  ← cover_bg, cover_logo, phiqus_logo (PDF)
│   │   ├── tiers/
│   │   │   ├── definitions.json
│   │   │   ├── registry.py
│   │   │   ├── basico.py
│   │   │   ├── pro.py
│   │   │   └── premium.py
│   │   └── v0/
│   │       ├── analytics/analytics_service.py
│   │       ├── payments/payment_service.py
│   │       └── reports/
│   │           ├── reports_service.py
│   │           ├── report_pdf_service.py
│   │           └── report_job_service.py
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
│   │   └── v0/
│   │       ├── llm/          (facade + adapters groq/openai/bedrock)
│   │       ├── bedrock/      (raw + processed; helpers LLM legacy path)
│   │       ├── besttime/     (raw + processed)
│   │       ├── google/       (raw + processed + google_auth + giro_filter)
│   │       ├── mercadopago/  (raw + processed + webhook_signature)
│   │       ├── s3/           (raw + processed)
│   │       ├── ses/          (raw + processed)
│   │       ├── tiles/        (raw + processed; mapas PDF)
│   │       └── database/     (raw = SQL/sesión; processed = tipado)
│   │
│   └── schemas/                     ← Contratos transversales (home único)
│       ├── auth_schemas.py
│       ├── domain/
│       └── v0/
│
├── scripts/
│   ├── README.md
│   ├── ingest_inegi/
│   ├── demografia/
│   ├── benchmark_metricas.py
│   ├── debug_analisis_cuantitativo.py
│   └── migrate_aliados_guiados.py
│
└── tests/
    ├── test_architecture_layers.py  ← Gate de fronteras (AST) + anti-shim
    ├── test_exceptions.py
    ├── test_endpoint_hardening.py   ← superficie HTTP / auth anónimo
    ├── test_session_auth.py         ← sesión, download token, mock auth
    ├── test_llm_provider.py
    └── …
```

### Lectura rápida para el revisor

| Ubicación | ¿Capa? | Nota |
|-----------|--------|------|
| `app/core/` | Transversal | Config / middleware / sesión / download tokens / `get_current_user` |
| `app/exceptions/` | Transversal | Errores user-centric |
| `app/routers/` | Sí | Entrada HTTP delgada; geo mapa público documentado |
| `app/services/` | Sí | Orquestación; reports solo en `v0/reports/`; `assets/` compartidos |
| `app/domain/` | Sí | Pura (sin I/O) |
| `app/clients/` | Sí | Solo árbol `v0/` (sin módulos flat) |
| `app/schemas/` | Transversal | Data contracts (sin paralelo en routers) |
| `scripts/` | Operación | CLI; no endpoints |

### Admin (alcance relacionado)

`geo-viabilidad-admin` aplica el mismo espíritu (sin ser el foco del RFC API):

* `admin/clients/` — `session_scope`, `get_engine`, queries de métricas
* `admin/exceptions/` — mensajes amigables al operador
* `admin/routes.py` — sin `SessionLocal()` / `engine` directos

---

## Detailed Design

### 1. Core (`app/core/`)

| Módulo | Responsabilidad |
|--------|-----------------|
| `config.py` | Flags (`DEV_MODE`, `PAYMENTS_MOCK`, `REPORTS_LOCAL_STORAGE`, `LLM_PROVIDER`), secretos de sesión, CORS allowlist, credenciales proveedores |
| `middleware.py` | Rate limit LLM; rate limit abuso en geo público; red de seguridad user-facing |
| `security.py` | `get_current_user`: cookie/`Bearer` de sesión; mock solo `DEV_MODE`; rechaza ID token Google en hot path |
| `session_tokens.py` | Emisión / verificación / revocación JWT de app (`jti`) |
| `download_tokens.py` | JWT corto one-time para descarga PDF (bound a `orden_id` + `sub`) |

### 2. Exceptions (`app/exceptions/`)

Catálogo tipado + `@app.exception_handler(UserFacingError)` en `main.py`. Middleware atrapa `OperationalError` / boto / `RequestException` no convertidos.

### 3. Routers (`app/routers/`)

HTTP delgado. Prefijos: `/api/auth`, `/api/pagos`, `/api/analizar`, `/api/reportes`. Health en `GET /health` (wiring en `main.py`; **no** filtra `dev_mode` / `payments_mock`).

Ejemplo de delgadez: `POST /api/analizar/previa` autentica → parsea body → `obtener_vista_previa_service(...)` → return.

Excepción documentada: geocoding del mapa sin auth (ver decisión de superficie pública).

### 4. Services (`app/services/`)

| Módulo | Responsabilidad |
|--------|-----------------|
| `auth_service.py` | Login Google → sesión; config auth pública |
| `v0/payments/` | Órdenes, preferencias MP, webhooks (firma en client), máquina de estados; mock gated por `PAYMENTS_MOCK` |
| `v0/analytics/` | Motor analítico; orquesta DB client + domain + Google; competencia HTTP |
| `v0/reports/` | Meta PDF, descarga con token, `report_pdf_service`, `report_job_service` (S3/SES vía clients) |
| `foda_service.py` | LLM facade + enrichment narrativo |
| `presentation/` | Gráficas, mapas (tiles client), afluencia, narrativa |
| `assets/` | Imágenes de portada/logo del PDF (consumidas desde `v0/reports`) |
| `tiers/` | Registry + strategies |

### 5. Domain (`app/domain/`)

SVA, NSE (desde raw), demografía (desde raw), keywords/merge de competencia, aliados, vigencia. **Sin `sqlalchemy`, sin `app.clients`.**

### 6. Clients (`app/clients/`)

Integraciones Raw + Processed **solo** bajo `clients/v0/`. No existen módulos flat de re-export en `clients/*.py`.

Proveedores: Google (+ auth ID token), BestTime, **LLM facade** (Groq/OpenAI/Bedrock), Mercado Pago (+ validación firma webhook), S3, SES, tiles, **database (PostGIS)**.

### 7. Schemas (`app/schemas/`)

Home único: `auth_schemas.py` canónico (sin paralelo en routers). `v0/` = contratos HTTP y DTOs de proveedores; `domain/` = TypedDicts internos.

### 8. Scripts

- CLIs documentados (`ingest_inegi/`, `demografia/`, `debug_analisis_cuantitativo.py`).
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
- [x] `schemas/auth_schemas.py`; shim en routers (luego eliminado)
- [x] Admin `clients/` + `exceptions/` + routes sin `SessionLocal`
- [x] `tests/test_architecture_layers.py` + `test_exceptions.py`
- [x] Docs `ARCHITECTURE.md` / drift `FRONTEND_DIR` en `REPO_SPLIT_AND_LAYERS.md`

### Auth / superficie HTTP (28–29 jul-2026)

- [x] Sesión JWT app + cookie HttpOnly `gv_session`; Google ID token solo en `/api/auth/google`
- [x] Mock Bearer (`mock-token` / `mock-jwt-*`) gated a `DEV_MODE=true`
- [x] Mapa: `geocodificar` + `buscar-direccion` públicos + rate limit; resto de `/api/analizar/*` con auth
- [x] PDF: sin mount `/static/reports`; descarga con `download_tokens` one-time
- [x] Webhook MP: firma en `clients/v0/mercadopago/mercadopago_webhook_signature.py`
- [x] CORS allowlist; `/docs` off si `DEV_MODE=false`; health sin flags de entorno
- [x] Flags documentados: `DEV_MODE` ≠ `PAYMENTS_MOCK` ≠ sandbox
- [x] Assets PDF resueltos desde `services/assets/` tras move a `v0/reports/`
- [x] Tests: `test_endpoint_hardening.py`, `test_session_auth.py`

### Limpieza shims (29-jul-2026)

- [x] Eliminados `clients/{google_auth,google_places,besttime,bedrock,mercadopago_client}.py`
- [x] Eliminados `services/{report_pdf_service,report_job_service}.py` (solo viven en `v0/reports/`)
- [x] Stress LLM apunta a `foda_service` + `clients/v0/bedrock`
- [x] Gate `TestNoFlatClientOrReportShims` en `test_architecture_layers.py`

---

## Consideraciones

### Seguridad de tiers (Luis)

* No confiar en `tier_id` del body para desbloquear features.
* Auth + orden pagada definen entitlement.
* Webhook idempotente; firma validada; contemplar timeout MP; doble clic / refresh.

### Seguridad de sesión y superficie (jul-2026)

* Producción: `DEV_MODE=false` (bloquea mock auth y docs), `PAYMENTS_MOCK=false`, `SESSION_SECRET` fuerte, CORS allowlist.
* No hace falta borrar código mock del repo: con flags off no es alcanzable.
* Revocación `jti` y tokens PDF one-time son **in-memory** hoy → frágil con multi-worker; documentado como follow-up (Redis/DB o sticky + un worker).
* Rate limit geo usa IP del peer; detrás de nginx conviene forwarded headers confiables.

### Equivalencia y fronteras (Pedro + Fase 1.5)

* Gate equivalencia: suite API en verde (`uv run pytest tests/ --ignore=tests/security`).
* Gate fronteras: AST tests — routers ↛ domain; clients/v0 ↛ services; domain ↛ sqlalchemy/clients.
* Gate superficie: `test_endpoint_hardening.py` + `test_session_auth.py`.
* Gate anti-shim: módulos flat `clients/*` y `services/report_*` no deben reaparecer.
* No añadir features de producto en este RFC.

### Residuos aceptados (corto plazo)

* Algunos `HTTPException` legacy aún en `payment_service` / auth (migración gradual a `UserFacingError`).
* Health en `GET /health` (no bajo prefijo `/api`); documentado en tests.
* Stores in-memory de `jti` (sesión / download).
* ~~Shims flat en clients/services~~ → **eliminados** (29-jul-2026).

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

### Feedback Luis + auth + shims

- [x] Un solo home de schemas; report PDF/job bajo `services/v0/reports/`
- [x] `LLM_PROVIDER` + facade `clients/v0/llm/`
- [x] Mock auth inerte con `DEV_MODE=false`
- [x] Solo geo de mapa (+ health/configs públicas) sin sesión
- [x] Checklist operativo: `docs/SECURITY_CHECKLIST.md`
- [x] Sin shims DEPRECATED flat; imports canónicos solo `v0/`

---

## Métricas

| Métrica | Antes (plano) | Tras Fase 1 | Tras Fase 1.5 (24-jul) | Tras feedback + auth + shims (29-jul) |
|---------|---------------|-------------|------------------------|--------------------------------------|
| Capas “extra” fuera del modelo | N/A | 0 (presentation/infra absorbidos) | 0 + `exceptions/` transversal | + `session_tokens` / `download_tokens` en core |
| Pureza de fronteras | N/A | Parcial (~48/100 auditoría) | Enforceada (AST + refactor) | Sin shims; superficie HTTP documentada |
| Estrategias de tier | 0 | basico/pro/premium | Sin cambio | Sin cambio |
| Clients v0 | Parcial | Google/Bedrock/BestTime/S3/DB | + MercadoPago, SES, tiles | + LLM facade; firma webhook MP; **sin flat** |
| Reports canónicos | plano | services root | services root | **solo** `services/v0/reports/` |
| Scripts VPS en repo API | sí | 0 | 0 | 0 |
| Tests equivalencia (sin security) | suite | ~79 passed | **145 passed** | + hardening/session/anti-shim |

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
- [x] ~~Shims flat (compat tests/security)~~ → **eliminados por completo** (29-jul-2026)
- [x] `report_pdf_service` y `report_job_service` bajo `services/v0/reports/`
- [x] Facade LLM en `clients/v0/llm/` con adapters groq/openai/bedrock + `LLM_PROVIDER` env
- [x] Debug cuantitativo: script CLI `scripts/debug_analisis_cuantitativo.py` (JSON + Excel) + endpoint DEV_MODE
- [x] SemVer 1.0.0 alineado; Commitizen config en `pyproject.toml`
- [x] README actualizado con: LLM_PROVIDER, debug dump, compose/run_local, middleware real, assets

---

## Apéndice — Endurecimiento auth / demo estabilizada (28–29 jul-2026)

Tras restaurar el flujo end-to-end (mapa + previa + PDF) se revalidó que el endurecimiento de capas HTTP no se hubiera revertido:

| Tema | Decisión / fix |
|------|----------------|
| Mapa sin login | Solo `geocodificar` + `buscar-direccion` públicos; rate-limited |
| Auth mock | Bloqueado si `DEV_MODE=false` (incluye `mock-jwt-admin`) |
| Flags | `DEV_MODE` (entorno) ≠ `PAYMENTS_MOCK` (checkout) ≠ sandbox MP |
| Portada PDF negra | Path de assets corregido a `services/assets/` desde `v0/reports/` |
| Checklist | `docs/SECURITY_CHECKLIST.md` para VPS/ngrok |

**Follow-ups conocidos (no bloquean capas):** store compartido para `jti` (multi-worker); IP cliente vía `X-Forwarded-For` confiable; acotar `?for=swagger` a `DEV_MODE`.

---

## Apéndice — Eliminación de shims (29-jul-2026)

Cierre del pedido de Luis (“un solo árbol de clients”) y home único para reports:

| Eliminado | Canónico |
|-----------|----------|
| `app/clients/google_auth.py` | `clients/v0/google/google_auth.py` |
| `app/clients/google_places.py` | `clients/v0/google/` |
| `app/clients/besttime.py` | `clients/v0/besttime/` |
| `app/clients/bedrock.py` | `clients/v0/bedrock/` (+ FODA en `services/foda_service`) |
| `app/clients/mercadopago_client.py` | `clients/v0/mercadopago/` |
| `app/services/report_pdf_service.py` | `services/v0/reports/report_pdf_service.py` |
| `app/services/report_job_service.py` | `services/v0/reports/report_job_service.py` |

Gate: `TestNoFlatClientOrReportShims` en `tests/test_architecture_layers.py`.

---

## Links

- Change OpenSpec Fase 1.5: `openspec/changes/enforce-layer-boundaries/`
- Change OpenSpec feedback Luis: `openspec/changes/address-luis-layer-feedback/`
- Checklist seguridad: `docs/SECURITY_CHECKLIST.md`
- Plan multi-repo: `docs/REPO_SPLIT_AND_LAYERS.md`
- Arquitectura monorepo: `docs/ARCHITECTURE.md`
- RFC API producto: `rfcs/rfc-geo-viabilidad-api.md`
- RFC paquete data: `rfcs/rfc-geo-viabilidad-data.md`
- Transcripción revisión 20-jul-2026: comentarios Pedro Hernández / Luis Ramos
- Check 27-jul-2026: feedback estructura (Luis Ramos)
- Check 28–29 jul-2026: auth sesión, superficie mapa, mock gated, assets PDF, **shims eliminados**