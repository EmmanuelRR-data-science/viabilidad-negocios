# Checklist de ciberseguridad GeoViabilidad (≥90%)

Usar antes de exponer la API por ngrok, VPS o producción.

## Flags de entorno (obligatorio en URL pública)

- [ ] `DEV_MODE=false`
- [ ] `PAYMENTS_MOCK=false` (salvo demo local explícita)
- [ ] `REPORTS_LOCAL_STORAGE=false` (usar S3 en prod)
- [ ] `SESSION_SECRET` ≥ 32 caracteres, distinto del default de desarrollo
- [ ] `CORS_ORIGINS` o `PUBLIC_APP_URL` con allowlist HTTPS
- [ ] `MERCADOPAGO_WEBHOOK_SECRET` configurado (panel MP → Webhooks)
- [ ] `GOOGLE_OAUTH_CLIENT_ID` configurado
- [ ] Sin secretos en el repo (solo `.env` / secrets manager)

## Superficie HTTP

- [ ] `/docs`, `/redoc`, OpenAPI deshabilitados fuera de DEV
- [ ] `/error-test` no usable fuera de DEV
- [ ] `/static/reports` no expuesto
- [ ] `/api/pagos/webhook-mock` ausente si `PAYMENTS_MOCK=false`
- [ ] Health no filtra `dev_mode` / `payments_mock`

## Auth / sesión

- [ ] Login Google solo en `POST /api/auth/google`
- [ ] SPA usa cookie HttpOnly `gv_session` (sin ID token Google en cada request)
- [ ] Logout revoca `jti` y limpia cookie
- [ ] PDF local requiere `?token=` firmado de un solo uso

## Red / host

- [ ] PostgreSQL sin puerto público a Internet
- [ ] UFW: solo 22 / 80 / 443
- [ ] HTTPS (ngrok o TLS) para cookies `Secure` y OAuth

## Smoke rápido

```bash
# Mapa público (geocode) → 200 (rate-limited); NO exige 401
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001/api/analizar/geocodificar?lat=19&lng=-99"
# Protegido anónimo → 401
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/analizar/previa
# Health limpio
curl -s http://localhost:8001/health
# Static reports → 404
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/static/reports/x.pdf
```

## Tests

```bash
cd geo-viabilidad-api
uv run pytest tests/test_endpoint_hardening.py tests/test_session_auth.py tests/test_api_vulnerability_surface.py -q
```
