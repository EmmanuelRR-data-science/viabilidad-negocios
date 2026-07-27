# Demo Checklist — address-luis-layer-feedback

## Test Results

| Suite | Result |
|---|---|
| `uv run pytest tests/ --ignore=tests/security -q` | **162 passed, 0 failed** |
| Warnings | 127 (deprecation only — `utcnow`, `on_event`, `httpx/starlette`) |

## Endpoint Smoke Tests (TestClient)

| Endpoint | Status | Notes |
|---|---|---|
| `GET /health` | **200 OK** | `{"status": "online", "service": "GeoViabilidad Hook Backend", ...}` |
| `GET /docs` | **200 OK** | Swagger UI renders |

## Architecture Validation

- [x] `app.routers.auth_schemas` deleted — `ImportError` confirmed by `test_no_routers_auth_schemas`
- [x] Hot-path imports use `app.clients.v0.*` — verified in analytics_service, foda_service, security, auth_service, report services
- [x] Flat shims (`clients/google_places`, `besttime`, `bedrock`, `google_auth`) are thin deprecated re-exports
- [x] Report services moved to `app/services/v0/reports/`
- [x] LLM facade at `app/clients/v0/llm/` with groq/openai/bedrock adapters
- [x] `LLM_PROVIDER` config in `app/core/config.py` + `.env.example`
- [x] Debug JSON+Excel script at `scripts/debug_analisis_cuantitativo.py`
- [x] DEV_MODE-only debug endpoint at `/api/analizar/debug/cuantitativo`
- [x] VERSION=1.0.0, pyproject version=1.0.0
- [x] Commitizen config in pyproject.toml
- [x] RFC appendix in `rfcs/rfc-api-layers.md`
