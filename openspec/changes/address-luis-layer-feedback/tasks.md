## 0. Branch y baseline

- [x] 0.1 Crear/usar rama de feature para este change (p. ej. `feat/address-luis-layer-feedback` desde la base acordada)
- [x] 0.2 Confirmar suite API en verde (`uv run pytest tests/ --ignore=tests/security`) y anotar baseline

## 1. Higiene schemas y clients

- [x] 1.1 Eliminar `app/routers/auth_schemas.py`; actualizar todos los imports a `app.schemas.auth_schemas`
- [x] 1.2 Grep hot paths: migrar imports restantes de `app.clients.<flat>` a `app.clients.v0.*`
- [x] 1.3 Eliminar o vaciar módulos flat `clients/*.py` que ya no se usen (dejar nota de deprecación solo si hace falta compat tests/security)
- [x] 1.4 Documentar en README/RFC: middleware real (`UserFriendlyExceptionMiddleware`, rate-limit) y rol de `services/assets/`

## 2. Versionar report services bajo v0

- [x] 2.1 Mover `report_pdf_service.py` y `report_job_service.py` a `app/services/v0/reports/`
- [x] 2.2 Actualizar imports en payments, analytics, tests y `__init__` de reports
- [x] 2.3 Documentar política: cambios aditivos en v0; breaking → nueva versión de paquete

## 3. Abstracción LLM intercambiable

- [x] 3.1 Diseñar/implementar facade `clients/v0/llm/` (o equivalente) con selección por env (`LLM_PROVIDER`)
- [x] 3.2 Adapter Groq/OpenAI para desarrollo local sin AWS
- [x] 3.3 Adapter Bedrock opcional (prod) detrás de la misma interfaz
- [x] 3.4 Cablear `foda_service` / callers para usar solo la facade (sin SDK Bedrock directo en services)
- [x] 3.5 Tests unitarios del registry/provider con mock

## 4. Debug cuantitativo sin IA

- [x] 4.1 Exponer dump JSON del análisis cuantitativo sin FODA (script CLI y/o endpoint `DEV_MODE`/admin)
- [x] 4.2 Implementar export Excel del payload cuantitativo (incluido en este change)
- [x] 4.3 Garantizar que el dump no bypassa entitlement de PDF pagado
- [x] 4.4 Documentar uso en README (cómo generar el JSON de debug)

## 5. Versionado SemVer y runbook

- [x] 5.1 Alinear `VERSION` y `pyproject.toml` a **`1.0.0`**
- [x] 5.2 Añadir documentación Commitizen / bump con `uv` (y config mínima si se aprueba instalarlo)
- [x] 5.3 Ampliar `geo-viabilidad-api/README.md`: compose/`run_local`, env mínimas, `/docs`, `/health`, pytest, RFC capas
- [x] 5.4 Actualizar apéndice breve en `rfcs/rfc-api-layers.md` con feedback Luis → este change

## 6. Verificación y entrega

- [x] 6.1 Suite API + tests arquitectura en verde (162 passed, 0 failures)
- [x] 6.2 Checklist demo Swagger (health, pagos/config, al menos un flujo analizar/pagos en mock)
- [x] 6.3 Ejecutar demo/checklist el agente (TestClient o server local); documentar resultados
- [x] 6.4 Preparar descripción de PR (summary + test plan); **no push/PR hasta que el usuario lo pida**
- [x] 6.5 Guardrails: sin dual schemas; sin flat clients en hot path; LLM vía facade; report_* bajo v0

## Decisiones de aprobación (resueltas)

- [x] Q1: Excel debug **en este change**
- [x] Q2: Env **`LLM_PROVIDER`**
- [x] Q3: SemVer **`1.0.0`**
