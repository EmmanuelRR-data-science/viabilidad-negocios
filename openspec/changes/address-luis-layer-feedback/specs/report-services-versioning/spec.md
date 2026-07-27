## ADDED Requirements

### Requirement: Report PDF and job services live under versioned reports package
`report_pdf_service` and `report_job_service` SHALL reside under `app/services/v0/reports/` (alongside `reports_service.py`) so that production-facing report orchestration is versioned with the same `v0` boundary as other business services.

#### Scenario: Import path for report job
- **WHEN** payments webhook or background task triggers PDF generation
- **THEN** it imports from `app.services.v0.reports` (not from a floating `app.services.report_job_service` at the services root)

### Requirement: Compatibility policy for report service changes
Changes to report PDF/job behavior under `v0` SHALL prefer additive changes (new tier strategies, new optional sections) over breaking rewrites of existing tier outputs. Breaking changes MUST bump to a new service version package (`v1`/`b1`) or be explicitly documented in the PR.

#### Scenario: New tier does not rewrite basico path
- **WHEN** a new commercial tier is added
- **THEN** existing basico/pro/premium report paths remain callable via the same `v0` APIs unless a version bump is declared
