## Why

La migración a carpetas por capas en `geo-viabilidad-api` ya ocurrió, pero la regla de dependencia unidireccional aún se viola: routers llaman clients/domain y consultan ORM, services ejecutan SQL/HTTP/SDK crudos, domain tiene I/O PostGIS, clients importan services, y no existe `app/exceptions/`. Sin cerrar esa pureza, el diseño por capas queda cosmético y dificulta tests, evolución y cumplimiento SDD.

## What Changes

- Adelgazar routers `analytics` y `reports` para que solo validen entrada, deleguen a services y retornen respuesta.
- Mover consultas PostGIS/SQL embebidas desde `domain/` y `services/` hacia `clients/v0/database` (raw/processed).
- Romper el ciclo `clients` → `services`: Bedrock deja de importar `foda_service`; el enrichment FODA queda en la capa de servicios.
- Introducir `app/exceptions/` con excepciones user-centric y dejar de filtrar `str(exc)` / códigos técnicos crudos al cliente.
- Unificar clientes externos en `clients/v0/*/raw|processed` y retirar (o reducir a re-export temporal) los módulos flat legacy.
- Extender el mismo patrón de capas a admin: `clients/` para acceso a datos, `exceptions/` para errores amigables, y routes sin `SessionLocal` directo.
- Actualizar `docs/ARCHITECTURE.md` (y drift menor en `REPO_SPLIT_AND_LAYERS.md`) para reflejar el árbol y reglas reales.

No hay cambios **BREAKING** de contrato HTTP públicos previstos: mismos endpoints y payloads; el refactor es interno de capas.

## Capabilities

### New Capabilities

- `layer-boundary-enforcement`: Reglas de dependencia routers → services → (domain puro | clients); prohibiciones de I/O en routers/domain y de clients→services.
- `user-centric-exceptions`: Catálogo `app/exceptions/` (y admin equivalente) con mensajes en lenguaje natural, logging técnico interno y mapeo HTTP sin filtrar tracebacks/`str(exc)`.
- `database-client-queries`: Consultas PostGIS/ORM de demografía, NSE, categorías y lecturas de órdenes encapsuladas en clients database processed (API) / clients admin.
- `client-stack-unification`: Un solo stack de integración externa vía `clients/v0` raw/processed; eliminación del uso productivo de clients flat legacy.

### Modified Capabilities

- (ninguna — no hay specs previas en `openspec/specs/`)

## Impact

- **Código:** `geo-viabilidad-api/app/routers/v0/{analytics,reports}.py`, `services/**`, `domain/{nse,demografia_segmentos,competencia_busqueda}.py`, `clients/**`, nuevo `app/exceptions/`; `geo-viabilidad-admin/admin/{routes,services}` + nuevos `clients/` y `exceptions/`.
- **APIs HTTP:** sin cambio de rutas/contratos; respuestas de error pasan a mensajes user-centric (posible cambio de texto de `detail`, no de shape estable documentado).
- **Dependencias:** sin nuevas librerías; mayor uso de `geo-viabilidad-data` vía clients; declarar dependencia explícita donde falte.
- **Docs/tests:** actualizar arquitectura; ajustar tests unitarios/integración por capa (mocks en clients, domain puro sin Session).
- **Fuera de alcance:** split multi-repo, cambios de features de producto, migraciones de esquema PostGIS, redesign de tiers.
