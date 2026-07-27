## ADDED Requirements

### Requirement: SemVer sources are aligned
`geo-viabilidad-api/VERSION` and `pyproject.toml` `[project].version` SHALL show the same SemVer string after this change’s version bump.

#### Scenario: Versions match
- **WHEN** a reviewer reads `VERSION` and `pyproject.toml`
- **THEN** both report the same version (target: code line representing layered API v1.x after this PR)

### Requirement: Version bump tooling is available
The API project SHALL document (and preferably configure) Commitizen or an equivalent `uv`-friendly bump workflow so maintainers can bump major/minor/patch consistently.

#### Scenario: Maintainer can bump
- **WHEN** a maintainer follows the README/versioning section
- **THEN** they can produce a SemVer bump without manually editing mismatched files

### Requirement: Runnable API README for the team
`geo-viabilidad-api/README.md` SHALL include: how to start via monorepo compose/`run_local`, required env vars (minimal), how to open Swagger (`/docs`), health check path, how to run pytest, and pointer to layer RFC.

#### Scenario: New reviewer boots API
- **WHEN** Luis or Pedro follows the API README
- **THEN** they can reach OpenAPI docs and a successful health response without undocumented tribal knowledge

### Requirement: PR checklist includes Swagger demo evidence
The change delivery SHALL include a short test plan (in PR body or `tasks.md`) with example calls (health, auth config, and at least one analizar/pagos path available in mock mode) suitable for a Swagger walkthrough without the SPA.

#### Scenario: Demo without front
- **WHEN** the review session focuses on Swagger
- **THEN** the PR/test plan lists the endpoints and expected mock-mode behavior
