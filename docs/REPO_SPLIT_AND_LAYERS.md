# Plan: multi-repo + arquitectura por capas

Documento de decisión y roadmap para pasar del monorepo actual a **tres repositorios independientes** con **versionado por release** y refactor **por capas** en la API.

Estado: **Fase 0.2 y Fase 1 en progreso** (jun 2026). Paquete `geo-viabilidad-data` creado; admin desacoplado; SPA servida por nginx (`web-spa`); capas pagos/auth en API.

---

## 0. Completado recientemente

- [x] Paquete **`geo-viabilidad-data`** (`models`, `database`, ingesta INEGI).
- [x] Admin importa `geo_viabilidad_data.*` (sin volumen `api/app` en compose).
- [x] Tests admin movidos a `geo-viabilidad-admin/tests/`.
- [x] Dockerfiles con build context en raíz del monorepo.
- [x] Web desacoplada de `FRONTEND_DIR`: servicio **`web-spa`** (nginx :8000) proxy a **`web-api`** (:8001 directo).
- [x] Capas API Fase 1 (pagos + auth): `clients/`, `services/`, `routers/`.
- [x] Capas API Fase 1b (analytics + reports): `domain/`, `presentation/`, `core/`, `schemas/domain/`, sin módulos legacy en `app/` raíz.

---

## 1. Diagnóstico del monorepo actual

### Lo que ya funciona

- Tres carpetas con stacks distintos identificados (`api` / `web` / `admin`).
- Un solo `docker-compose.yml` levanta el stack completo para desarrollo.
- Documentación de árbol real en `docs/ARCHITECTURE.md`.

### Lo que limita legibilidad, escala y releases

| Problema | Evidencia en el repo |
|----------|---------------------|
| **Un solo versionado** | Un tag/commit en `main` del monorepo implica versión única para API, web y admin aunque solo cambie uno. |
| **Stacks mezclados** | FastAPI (`uv`, Ruff, PostGIS, Bedrock) vs Flask (Jinja, ingesta fiona) en el mismo repo y CI implícito. |
| **Acoplamiento admin → API** | ~~Resuelto~~ con `geo-viabilidad-data`. |
| **Acoplamiento API → web** | ~~FastAPI sirve la SPA vía `FRONTEND_DIR`~~ → resuelto con `web-spa` (nginx). |
| **Tests cruzados** | ~~Resuelto~~: tests admin en su carpeta. |
| **API plana** | ~30 módulos en `app/` mezclan HTTP, orquestación, dominio e integraciones sin fronteras importables. |

---

## 2. Objetivo arquitectónico

```
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  geo-viabilidad-web │  │  geo-viabilidad-api │  │ geo-viabilidad-admin│
│  (repo)             │  │  (repo)             │  │  (repo)             │
│  HTML/CSS/JS        │  │  FastAPI + capas    │  │  Flask              │
│  v1.4.0             │  │  v2.1.0             │  │  v0.8.0             │
└──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘
           │ REST /api/*             │ SQL                    │ SQL
           └────────────────────────►│◄───────────────────────┘
                                     ▼
                              ┌──────────────┐
                              │   PostGIS    │
                              └──────────────┘
        ▲
        │ pip: geo-viabilidad-data
   API + Admin
```

Despliegue e infraestructura (VPS, nginx, compose de producción) queda a cargo de otro equipo; no hay repo `infra` en este producto.

### Principios

1. **Un repo = un artefacto desplegable = una línea de versión SemVer.**
2. **Contratos explícitos** entre repos (OpenAPI, env vars documentadas); sin imports Python cruzados.
3. **Capas en la API** con regla de dependencia unidireccional.
4. **Admin no importa código de la API**; comparte solo esquema de BD (o llama endpoints internos en fases tardías).

---

## 3. Repositorios propuestos

| Repo | Contenido | Release artifact |
|------|-----------|------------------|
| `geo-viabilidad-api` | FastAPI, motor analítico, pagos, PDF, jobs | Imagen Docker `api:2.x.y` |
| `geo-viabilidad-web` | SPA estática | Carpeta estática / S3 / `web:1.x.y` |
| `geo-viabilidad-data` | ORM, PostGIS, ingesta INEGI (pip) | Paquete `0.x.y` en PyPI privado / Git tag |

### Versionado por release (cada repo)

- Archivo fuente: `VERSION` en raíz o `pyproject.toml` / `package.json`.
- Flujo en `main`:
  1. PR mergeado con Conventional Commits (`feat:`, `fix:`, `BREAKING CHANGE:`).
  2. CI calcula bump SemVer (o release manual con `workflow_dispatch`).
  3. Tag `v2.1.0` **solo en ese repo**.
  4. Build y push de imagen/artefacto con ese tag.
- **Matriz de compatibilidad** en `geo-viabilidad-infra` (ejemplo):

  | Stack | API | Web | Admin |
  |-------|-----|-----|-------|
  | prod 2026-06 | ≥2.0.0 | ≥1.3.0 | ≥0.5.0 |

---

## 4. Desacoplar antes del split (Fase 0 — obligatoria)

Hacer esto **dentro del monorepo** para que el `git filter-repo` o la extracción no rompa nada.

### 4.1 Admin deja de importar `app.*` de la API

**Hoy** (`geo-viabilidad-admin`):

```python
from geo_viabilidad_data.database import SessionLocal, engine
from geo_viabilidad_data.models import OrdenPago, AppUsuario
from geo_viabilidad_data.ingest_nacional import ingest_state, get_demografia_stats
```

**Opciones (elegir una):**

| Opción | Pros | Contras |
|--------|------|---------|
| **A. Paquete compartido `geo-viabilidad-data`** (pip editable / Git dep) | Un solo ORM e ingesta; DRY | Cuarto artefacto Python; versionar el paquete |
| **B. Duplicar solo `models` + SQL en admin** | Repos 100 % independientes | Riesgo de drift de esquema |
| **C. Admin consume API REST interna** (`/internal/ingest`) | Frontera limpia | Más latencia; auth servicio-a-servicio |

**Recomendación:** **A** para corto plazo (paquete `geo-viabilidad-data` con `models`, `database`, `ingest_*`), publicado desde el repo API o repo propio `geo-viabilidad-data`. Admin/API declaran `geo-viabilidad-data` vía `[tool.uv.sources]` (path editable en monorepo). Al split, el paquete puede quedarse en PyPI privado o como submodule hasta migrar a C.

### 4.2 Web deja de montarse dentro de la API

- Desarrollo: nginx local o `vite serve` / servidor estático en `:3000` con proxy a API.
- Producción: S3 + CloudFront (ya previsto en RFC) o nginx sirviendo `/` y proxy `/api` → FastAPI.
- Eliminar dependencia de `FRONTEND_DIR` en `main.py` cuando web tenga su propio despliegue.

### 4.3 Tests por ownership

- Mover `test_admin_flask.py` → `geo-viabilidad-admin/tests/`.
- API `conftest.py` solo con rutas del repo API.
- Contratos API: tests de esquema OpenAPI o colección Postman en repo `infra` o `api`.

---

## 5. Arquitectura por capas (API)

### Regla de dependencias

```
routers  →  services  →  domain
                ↓           ↑
            clients    infrastructure
                ↓
            schemas (dto / api)
```

- **routers:** HTTP delgado, auth, status codes, sin lógica de negocio.
- **services:** orquestación, transacciones, reglas de tier y pagos.
- **domain:** funciones puras (SVA, NSE, scoring, normalización).
- **clients:** HTTP/SDK (Google, MP, BestTime, Bedrock); sin SQL.
- **infrastructure:** SQLAlchemy models, repos, migraciones.
- **schemas:** Pydantic entrada/salida; separar `api` vs `domain` DTOs.

### Mapa de migración (módulos actuales → capas)

| Actual (`app/`) | Capa destino |
|-----------------|--------------|
| `routes_auth.py`, `routes_analytics.py` | `routers/` |
| `payments.py` (endpoints) | `routers/payments.py` |
| `payments.py` (lógica MP, órdenes) | `services/payment_service.py` |
| `analytics.py` | `services/analytics_service.py` |
| `tasks.py` | `services/report_job_service.py` + worker entry |
| `reports.py` | `services/report_pdf_service.py` |
| `sva_calculo.py`, `nse.py`, `aliados_*`, `competencia_*`, `demografia_*`, `vigencia_*`, `seleccion_atractores.py` | `domain/` |
| `google_places.py`, `besttime.py`, `bedrock.py` | `clients/` |
| `models.py`, `database.py` | `infrastructure/` |
| `schemas*.py` | `schemas/api/`, `schemas/domain/` |
| `ingest_*` | `services/ingest/` o paquete `geo-viabilidad-data` |
| `config.py`, `middleware.py` | `core/` o raíz `app/` |

### Tiers (extensibilidad)

```
app/tiers/
├── definitions.yaml      # basico, pro, premium — precios y features
├── registry.py
└── strategies/
    ├── basico.py
    ├── pro.py
    └── premium.py
```

Un solo endpoint `POST /api/v0/pagos/preferencia` con `tier_id`; el registry resuelve precio y capacidades del reporte.

---

## 6. Roadmap por fases

### Fase 0 — Preparación en monorepo (2–3 sprints)

- [ ] Extraer paquete `geo-viabilidad-data` (models + database + ingest) o equivalente.
- [ ] Admin consume el paquete; quitar volumen `geo-viabilidad-api/app` del compose admin.
- [ ] Mover tests admin al folder admin.
- [ ] Documentar OpenAPI como contrato estable (`/api/openapi.json`).
- [ ] Añadir `VERSION` + workflow release en cada carpeta (aún en monorepo, tags prefijados `api-v*`, `web-v*`).

### Fase 1 — Refactor por capas en API (sin split)

- [ ] Crear estructura `routers/`, `services/`, `clients/`, `domain/`, `infrastructure/`.
- [ ] Migrar **pagos** y **auth** primero (fronteras claras, muchos tests).
- [ ] Migrar **analytics** + **reports** (módulos más grandes).
- [ ] Introducir `tiers/` y sustituir `PRECIOS_TIER` hardcodeado.
- [ ] Mantener re-exports temporales en módulos viejos para no romper imports.

### Fase 2 — Split de repositorios

- [ ] Crear repos GitHub vacíos con historial (`git filter-repo` por carpeta o subtree split).
- [ ] Repo `geo-viabilidad-data` como repo Git propio (o publicar paquete versionado).
- [ ] Split git de api / web / admin.

### Fase 3 — Releases y operación

- [ ] Automatizar SemVer en merge a `main` por repo.
- [ ] Matriz de compatibilidad en infra.
- [ ] Changelogs por repo (`CHANGELOG.md`).
- [ ] (Opcional) Admin deja el paquete `data` y usa solo API + BD read-only.

---

## 7. Orden recomendado de trabajo

```
Fase 0 (desacoplar)  →  Fase 1 capas en API  →  Fase 2 split git  →  Fase 3 CI/release
         ↑                      ↑
    NO hacer split antes de cerrar estos dos bloques
```

**Razón:** si se hace el split hoy, el admin sigue necesitando el volumen Docker de `app/` y el versionado seguirá acoplado en la práctica.

---

## 8. Alcance fuera del producto

| Elemento | Responsable |
|----------|-------------|
| VPS, nginx, firewall, despliegue producción | Otro equipo / operaciones |
| `docker-compose.prod.yml` | Referencia histórica; no mantener scripts VPS en este repo |

El monorepo conserva `docker-compose.yml` solo para **desarrollo local**.
| `geo-viabilidad-api/backups/` | Storage fuera de git (S3 / servidor) |

---

## 9. Criterios de “listo para split”

1. `docker-compose` admin **sin** volumen `./geo-viabilidad-api/app`.
2. API **sin** `FRONTEND_DIR` en producción.
3. Al menos **pagos + auth + health** migrados a `routers/` + `services/`.
4. Tests pasan **por carpeta** sin `sys.path` al hermano.
5. Cada carpeta tiene `VERSION` y README de despliegue autónomo.

---

## 10. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Drift de esquema BD admin vs API | Paquete `data` versionado o migraciones únicas en API |
| Romper despliegue VPS actual | Infra repo fija tags compatibles; despliegue blue/green |
| Refactor infinito | Migrar por vertical (pagos, luego analytics); re-exports legacy con deprecation |
| Tres PRs para un feature full-stack | Convención “feature branch” con links cruzados en PR + matriz de compatibilidad |

---

## Referencias

- Árbol actual: `docs/ARCHITECTURE.md`
- Acoplamiento admin documentado: `geo-viabilidad-admin/README.md`
- Compose: `docker-compose.yml`
