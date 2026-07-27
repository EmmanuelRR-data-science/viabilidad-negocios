## ADDED Requirements

### Requirement: Routers remain HTTP-thin
Routers in `geo-viabilidad-api` SHALL only validate request input via Pydantic schemas, invoke service-layer functions, map service outcomes to HTTP responses, and MUST NOT import domain modules for business logic, call external clients directly, execute ORM/SQL queries, or assemble business response payloads beyond passing through service results.

#### Scenario: Analytics endpoints delegate to services
- **WHEN** a client calls an analytics endpoint under `/api/analizar/*` or related analytics routes
- **THEN** the router delegates to `services` and does not import or call `app.clients.*` or `app.domain.*` for business work

#### Scenario: Reports download does not query ORM in the router
- **WHEN** a client requests a local or remote report download
- **THEN** the router does not call `db.query` / SQLAlchemy models directly and obtains authorization and file resolution from a service

### Requirement: Services do not perform raw infrastructure I/O
Service modules SHALL orchestrate business logic using `domain` (pure) and `clients` (raw/processed) and MUST NOT embed raw SQL strings via `sqlalchemy.text`, call `boto3`/`requests`/`httpx` directly, or import routers.

#### Scenario: Demography/NSE data access goes through database clients
- **WHEN** analytics or report generation needs PostGIS demography or NSE aggregates
- **THEN** the service obtains typed/processed results from `clients/v0/database` (or equivalent processed API) rather than executing SQL inline

#### Scenario: Report job storage uses S3 client
- **WHEN** a report job uploads a PDF or generates a presigned URL
- **THEN** the service uses `clients/v0/s3` processed/raw APIs and does not instantiate `boto3.client` inline

### Requirement: Domain modules remain pure
Modules under `app/domain/` SHALL contain pure domain calculations and rules and MUST NOT import SQLAlchemy sessions, execute SQL, or call HTTP/SDK clients.

#### Scenario: NSE and demography scoring without Session
- **WHEN** NSE or demographic segment scoring is invoked
- **THEN** the domain function receives already-fetched data structures (dicts/schemas) and does not accept or use a DB `Session` for queries

#### Scenario: Competitor search orchestration leaves HTTP to clients via services
- **WHEN** competitor discovery is required
- **THEN** domain may score/filter in-memory results but MUST NOT import Google Places clients; services coordinate client fetches

### Requirement: Clients must not depend on services
Client modules under `app/clients/` MUST NOT import `app.services.*`. Enrichment and business post-processing SHALL live in the service layer.

#### Scenario: Bedrock client returns model output without FODA enrichment
- **WHEN** Bedrock processed client returns LLM content for FODA
- **THEN** it does not import `foda_service`; services apply FODA enrichment after receiving client output

### Requirement: Admin follows the same dependency direction
Admin routes SHALL open no DB sessions directly and SHALL delegate to services; services SHALL access persistence through an admin `clients/` layer (or `geo-viabilidad-data` behind that layer), not mix unstructured SQL across route handlers.

#### Scenario: Dashboard route does not open SessionLocal
- **WHEN** an admin dashboard or list page is rendered
- **THEN** the route handler does not call `SessionLocal()` itself and obtains view data from a service
