# Geo Viabilidad — Web

SPA pública (HTML/CSS/JS). En desarrollo local la sirve **nginx** (`web-spa` en Docker) y hace proxy de `/api/` hacia la API.

## URLs locales

- SPA: http://localhost:8000
- API (directo): http://localhost:8001/docs
- API (vía nginx): http://localhost:8000/docs

## Próximo paso

Consumir `GET /api/v0/tiers` cuando exista el catálogo centralizado (refactor de capas).
