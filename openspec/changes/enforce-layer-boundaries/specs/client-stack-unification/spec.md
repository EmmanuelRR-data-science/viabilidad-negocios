## ADDED Requirements

### Requirement: External integrations use v0 raw/processed clients
Productive code paths for Google Places/Auth, BestTime, Bedrock, and S3 SHALL import from `app.clients.v0.<vendor>.*_raw` / `*_processed` (or a thin package facade that re-exports those modules). New feature code MUST NOT add logic to legacy flat modules under `app/clients/*.py`.

#### Scenario: Analytics geocoding uses v0 Google processed
- **WHEN** geocoding or reverse geocoding is required from a service
- **THEN** the call goes through `clients/v0/google` processed APIs

#### Scenario: Report PDF AI narrative uses v0 Bedrock
- **WHEN** report generation invokes Bedrock
- **THEN** it uses `clients/v0/bedrock` and not business logic inside legacy `clients/bedrock.py` beyond temporary re-exports during migration

### Requirement: MercadoPago follows the same client pattern
MercadoPago integration SHALL be organized as raw + processed clients under `clients/v0/` (or equivalent versioned path). Routers MUST NOT import MercadoPago helpers for business parsing beyond what a service exposes; webhook parsing belongs in client/service layers consistently with other vendors.

#### Scenario: Webhook payment id extraction
- **WHEN** a MercadoPago webhook is received
- **THEN** payment id extraction occurs in the MercadoPago client (raw/processed) and the router only passes the request body to a payment service

### Requirement: Legacy flat clients are retired from hot paths
After migration, hot paths (analytics, payments, reports, report jobs, auth) MUST NOT import `app.clients.google_places`, `app.clients.bedrock`, `app.clients.besttime`, or `app.clients.mercadopago_client` except via deprecated re-export shims that forward to v0. Shims MAY exist temporarily and SHALL be removed or emptied before change completion if feasible without breaking external scripts.

#### Scenario: Grep-clean hot path imports
- **WHEN** the change is marked complete for client unification
- **THEN** services and routers used in production request paths import only `clients.v0` (or approved facades), not legacy flat modules for new logic

### Requirement: Documentation matches the client layout
Architecture documentation SHALL describe `clients/v0/*/raw|processed` as the canonical integration layout and MUST NOT claim obsolete flat-only or incorrect `infrastructure/`/`presentation/` roots without noting the actual `services/presentation` and `services/tiers` locations.

#### Scenario: ARCHITECTURE.md tree is accurate
- **WHEN** a developer reads `docs/ARCHITECTURE.md` after this change
- **THEN** the documented tree matches the repository layout for clients, presentation, tiers, and assets
