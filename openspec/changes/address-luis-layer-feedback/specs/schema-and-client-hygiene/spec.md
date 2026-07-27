## ADDED Requirements

### Requirement: Auth schemas live only under schemas/
The API SHALL keep authentication-related Pydantic models exclusively under `app/schemas/` (e.g. `schemas/auth_schemas.py`). Routers and services MUST import from `app.schemas` and MUST NOT keep a parallel `routers/auth_schemas.py` module (shim or otherwise).

#### Scenario: Single import path for auth DTOs
- **WHEN** a developer needs auth request/response models
- **THEN** the only module path is under `app.schemas` and `app.routers.auth_schemas` does not exist

### Requirement: Hot-path clients use only clients/v0
Productive routers and services SHALL import external integrations from `app.clients.v0.*`. Flat modules under `app/clients/*.py` MUST be removed or reduced to empty/deprecated stubs that are not imported by hot paths.

#### Scenario: No dual Bedrock entrypoints in hot path
- **WHEN** analytics, report job, or FODA orchestration needs an LLM or Places client
- **THEN** imports resolve to `clients/v0/...` and not to legacy flat `clients/bedrock.py` / `clients/google_places.py` for new logic

### Requirement: Middleware and assets are documented
Project documentation (API README and/or `rfc-api-layers.md`) SHALL state that `core/middleware.py` contains real middleware (user-facing errors, LLM rate limit) and that `services/assets/` holds PDF cover/logo assets as a **module** of services (not a separate architecture layer).

#### Scenario: Reviewer finds middleware purpose
- **WHEN** a reviewer opens the API README or RFC layers doc
- **THEN** they can see what each middleware does and why assets live under services
