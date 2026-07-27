Author(s): Emmanuel Ramírez Romero · revisión Pedro Hernández · Luis Ramos
Status: En revisión (alineado con rfc-api-layers tras check 20-jul-2026)
Ultima actualización: 2026-07-21

---

# RFC: Módulo API (geo-viabilidad-api)

## Objetivo

Definir la arquitectura técnica y responsabilidades del backend RESTful de **GeoViabilidad Negocios**. Este componente actúa como el motor analítico central y orquestador del ciclo de negocio (evaluación de puntos geográficos, gestión transaccional de pagos, ejecución asíncrona de reportes y generación de PDFs con soporte cualitativo por IA).

La organización interna por capas (routers → services → domain / clients / schemas) y los ajustes post-revisión Pedro/Luis se detallan en [`rfc-api-layers.md`](rfc-api-layers.md). Este RFC describe el **módulo de producto**; aquel formaliza el **refactor técnico de fronteras**.

---

## Goals

* Orquestar en un pipeline unificado demografía censal, competencia local, afluencia y razonamiento por IA.
* Desacoplar tareas costosas (PDF, SES, S3) de la respuesta HTTP mediante `BackgroundTasks`.
* Controlar capacidades por tier (Básico / Pro / Premium) con **estrategias server-side** (`services/tiers/basico|pro|premium`), usando la orden de pago como fuente de verdad — no el body del front.
* Exponer contratos REST documentados (OpenAPI) con middleware de errores user-centric y rate-limit de LLM.
* Mantener arquitectura por capas con dependencias unidireccionales (ver `rfc-api-layers.md`).
* Conservar equivalencia funcional tras el refactor (suite de tests en verde; gate documentado en el RFC de capas).

---

## Non-Goals

* Definir ORM primario ni ingesta masiva INEGI (delegado a `geo-viabilidad-data`; CLIs en `scripts/ingest_inegi/`).
* Servir la SPA en producción (CloudFront/S3 o nginx; la API no es el CDN del front).
* Almacenar tarjetas ni procesar cobros internos (Mercado Pago Checkout Pro).
* Orquestar hardening VPS / firewall (fuera de este repo; scripts `vps-*` eliminados de la API).
* Refactorizar fronts (`geo-viabilidad-web`, `geo-viabilidad-admin`).
* Añadir o quitar funcionalidades de negocio en el refactor de capas (solo reubicar y clarificar).

---

## Background

El sistema original era un backend plano: rutas HTTP mezclaban SQL espacial, APIs externas síncronas y manipulación de archivos. Se migró a un artefacto independiente con capas y, tras la revisión del 20-jul-2026, se ajustó el modelo:

* **Presentation** (gráficas, mapas, narrativa PDF) no es capa propia → módulo de `services/`.
* **Infrastructure** (PostGIS) no es capa propia → cliente en `clients/v0/database/` (raw + processed).
* **Tiers** viven en `services/tiers/` con estrategias explícitas por plan.
* **Scripts** operativos documentados, agrupados (`ingest_inegi/`, `demografia/`), solo shell (+ WSL).

---

## Overview

Implementación en **Python** con **FastAPI**, contenerizada en Docker. Dos flujos principales:

1. **Síncrono (vista previa):** estimación rápida de un punto (coordenadas, giro) con métricas básicas que motivan la compra.
2. **Asíncrono (post-pago):** webhook/retorno MP → `BackgroundTasks` → Places / BestTime / Bedrock (según estrategia del tier) → PDF (6 / 10 / 13 páginas) → S3 → SES → panel.

```mermaid
flowchart TD
    SPA[SPA / geo-viabilidad-web] -->|HTTP REST| API[geo-viabilidad-api]
    Admin[geo-viabilidad-admin] -->|BD vía geo-viabilidad-data| DB[(PostGIS)]

    subgraph apiLayers [geo-viabilidad-api]
        Routers[routers/] --> Services[services/]
        Services --> Domain[domain/]
        Services --> Clients[clients/]
        Services --> Tiers[tiers basico|pro|premium]
        Services --> Presentation[presentation + assets]
    end

    Clients -->|database raw/processed| DB
    Clients -->|APIs| External[Google · BestTime · Bedrock · MP · S3]
    SPA --> Routers
```

### Capas (resumen)

| Ubicación | Rol |
|-----------|-----|
| `routers/` | HTTP delgado: validar, autenticar, delegar |
| `services/` | Orquestación; incluye `presentation/`, `assets/`, `tiers/` |
| `domain/` | Reglas puras (SVA, NSE, competencia, aliados) |
| `clients/` | Fuentes externas: APIs + **PostGIS** (`v0/database`) |
| `schemas/` | Contratos Pydantic/TypedDict transversales |
| `core/` | Config, middleware, seguridad |
| `scripts/` | CLIs de servidor (no API pública) |

Detalle y regla de dependencias: [`rfc-api-layers.md`](rfc-api-layers.md).

---

## Detailed Design

### 1. Estructura y responsabilidades

* **`main.py`**: FastAPI, middleware (CORS, errores user-centric, rate-limit LLM), registro de routers.
* **Analytics (`services/v0/analytics/`)**: motor de demografía, NSE, competencia, atractores, afluencia y SVA; capacidades moduladas por `get_tier_strategy(tier)`.
* **Pagos (`services/v0/payments/`)**: preferencias Checkout Pro, webhooks, idempotencia; **monto y tier desde registry/estrategia** (servidor). Webhook valida consistencia de monto vs catálogo.
* **Reportes**: `report_job_service` (pipeline post-pago) + `report_pdf_service` (ReportLab) consumen `services/presentation/` y `services/assets/`.
* **Tiers (`services/tiers/`)**: `definitions.json` + `BasicoTierStrategy` / `ProTierStrategy` / `PremiumTierStrategy` (Bedrock, mapa, aliados guiados, páginas PDF).

### 2. Entitlement por tier (seguridad)

Flujo de autoridad (anti-manipulación del request):

```
Front declara intención de compra (tier_id)
  → Router autentica usuario
  → payment_service crea OrdenPago con monto del registry
  → Mercado Pago confirma pago (webhook)
  → OrdenPago = fuente de verdad del tier
  → report_job / analytics / PDF usan get_tier_strategy(orden.tier_adquirido)
```

El front no desbloquea capacidades; el servicio decide según orden + estrategia.

### 3. Gestión de dependencias

* **uv** obligatorio (`uv.lock`, `pyproject.toml`).
* **Ruff** para lint y formato.

### 4. Clientes externos (`clients/`)

Patrón **Raw** (transporte) + **Processed** (DTOs) bajo `clients/v0/` cuando aplica:

| Cliente | Uso |
|---------|-----|
| Mercado Pago | Preferencias Checkout Pro, webhooks / IPN |
| Google Places / Auth | Establecimientos, geocodificación, vigencia, login |
| BestTime | Curvas horarias / afluencia |
| Bedrock / Groq | FODA y narrativa (solo si la estrategia del tier lo permite) |
| S3 | Persistencia y URL firmada del PDF |
| **database** | Sesión PostGIS + modelos ORM vía `geo_viabilidad_data` |

### 5. Scripts operativos

| Carpeta | Contenido |
|---------|-----------|
| `scripts/ingest_inegi/` | Ingesta nacional y censo/NSE (CLI) |
| `scripts/demografia/` | dump / restore / sync (`.sh`, WSL en Windows) |

Ver `geo-viabilidad-api/scripts/README.md`. Sin scripts `vps-*` en este repositorio.

### 6. Seguridad e infraestructura

* Credenciales solo por variables de entorno (código agnóstico al ambiente).
* En producción, PostGIS solo en red interna Docker (sin puerto DB a internet).
* Rate-limit de endpoints LLM en middleware.
* Errores técnicos en logs; al usuario mensajes claros y accionables.

---

## Consideraciones

* **Admin** no importa `app.*` de la API; comparte esquema vía paquete `geo-viabilidad-data`.
* **Split a 3 repos** (web / api / admin): acordado; roadmap en `docs/REPO_SPLIT_AND_LAYERS.md`. Este RFC no ejecuta el split.
* Equivalencia post-refactor: suite sin `tests/security` en verde (79 passed al 21-jul-2026); detalle en `rfc-api-layers.md`.

---

## Métricas

Baseline medido con `scripts/benchmark_metricas.py` contra el VPS (`http://135.181.30.179:8000`) el **2026-06-19**. Punto de prueba: CDMX (19.43, −99.13), radio 1 km, rubro `cafeteria`. Artefacto: `scripts/benchmark_metricas_result.json`.

> Para refrescar (stack local o VPS arriba):  
> `PYTHONPATH=. uv run python scripts/benchmark_metricas.py --base-url http://localhost:8001`

### PostGIS (local / misma máquina que el benchmark)

| Operación | p50 |
|-----------|-----|
| Postgres ping (`SELECT 1`) | **2 ms** |
| Demografía ponderada (`ST_Intersects`) | **61 ms** |
| Cálculo NSE | **26 ms** |
| Cruce rubro → categoría | **2 ms** |

### Endpoints HTTP (VPS)

| Endpoint / flujo | p50 / medido | Notas |
|------------------|--------------|-------|
| `GET /health` | **448 ms** (p95 646 ms) | RTT + contenedor remoto |
| `POST /api/analizar/previa` | **~4.7 s** | Análisis completo de página (Places + PostGIS + motor) |
| `GET /api/analizar/buscar-direccion` | **~433 ms** | Geocoding; en esa corrida respondió 422 (validar query/auth al refrescar) |
| `POST /api/pagos/preferencia` | **212 ms** | Alta de orden + preferencia (mock o MP) |

### Flujo post-pago → dashboard → PDF (tier Básico, mock)

| Paso | Tiempo |
|------|--------|
| Desbloqueo post-pago (`webhook-mock`) | **713 ms** |
| Primer `GET /api/analizar/resultado/{id}` | **~4.3 s** |
| PDF listo (`/api/analizar/pdf/{id}`, polling) | **~2.9 s** desde el inicio del poll |
| Resultado con caché (segunda lectura) | **428 ms** |

### Lectura para el producto

* La **vista previa** (~5 s) está dominada por APIs externas (Places), no por PostGIS (<100 ms).
* Tras el pago, el **dashboard** puede servir en ~4 s la primera vez; con caché de orden baja a **sub-segundo**.
* La **generación de PDF** en background se solapa con el poll; el usuario percibe PDF disponible en el orden de **pocos segundos** tras el desbloqueo (Básico; Pro/Premium suman Bedrock/mapa/afluencia y suelen ser mayores).
* Objetivos de calidad: mantener previa &lt; ~8 s p95 en condiciones normales de red; resultado con caché &lt; 1 s; no bloquear el webhook mientras corre el job.

### Gate de refactor (equivalencia)

| Gate | Estado (21-jul-2026) |
|------|----------------------|
| Ruff `app` / `tests` / `scripts` | OK |
| Suite unitaria (sin `tests/security`) | **79 passed** |

---

## Links

* Capas y spike Pedro/Luis: [`rfc-api-layers.md`](rfc-api-layers.md)
* Plan multi-repo: `docs/REPO_SPLIT_AND_LAYERS.md`
* Arquitectura monorepo: `docs/ARCHITECTURE.md`
* Paquete data: [`rfc-geo-viabilidad-data.md`](rfc-geo-viabilidad-data.md)
* Web / Admin: [`rfc-geo-viabilidad-web.md`](rfc-geo-viabilidad-web.md), [`rfc-geo-viabilidad-admin.md`](rfc-geo-viabilidad-admin.md)
