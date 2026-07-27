## ADDED Requirements

### Requirement: PostGIS demography queries live in database clients
All PostGIS/SQL queries that aggregate demography within a radius (or equivalent spatial filters) SHALL be implemented in `clients/v0/database` raw and exposed as typed/normalized results via the processed client. Services and domain MUST NOT embed these SQL strings.

#### Scenario: Weighted demography fetch
- **WHEN** analytics needs población/demografía ponderada for a lat/lng/radius
- **THEN** it calls a processed database client method and receives a structured result suitable for domain scoring

### Requirement: NSE spatial queries live in database clients
NSE-related SQL currently in `domain/nse.py` SHALL move to database clients. Domain NSE logic SHALL operate on fetched records/aggregates without a SQLAlchemy `Session`.

#### Scenario: NSE calculation after fetch
- **WHEN** NSE is calculated for a location
- **THEN** the service fetches AGEB/NSE rows via the database processed client and passes data into a pure domain function

### Requirement: Category and order reads use client APIs
Lookups such as `categorias_cruce` resolution and order payment reads used by analytics/reports/payments/auth SHALL be available through database processed client methods (repository-style) rather than ad-hoc `db.query` / `text()` inside services or routers.

#### Scenario: Google type resolution
- **WHEN** analytics resolves a rubro to a Google Places type via `categorias_cruce`
- **THEN** the lookup is performed in the database client layer

#### Scenario: Report authorization data
- **WHEN** reports need order payment state for download authorization
- **THEN** the service obtains the order through a database client API, not via router-level ORM

### Requirement: Admin persistence access is centralized
Admin SQL/ORM currently scattered in services SHALL be reachable through an admin clients layer wrapping `geo-viabilidad-data`, including metrics, orders, leads, and ingest status queries.

#### Scenario: Metrics fetch via admin client
- **WHEN** the admin dashboard loads KPIs
- **THEN** the service calls an admin client/query module rather than embedding unbounded new SQL in the route
