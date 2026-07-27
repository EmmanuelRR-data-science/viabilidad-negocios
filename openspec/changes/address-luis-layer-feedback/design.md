## Context

Check semanal EDM (27-jul-2026, Fathom). Luis Ramos revisó la estructura post-`enforce-layer-boundaries`: la carpeta se ve bien, pero hay fricción de claridad (schemas/clients duplicados), riesgo de acoplar desarrollo a Bedrock/AWS, PR monolítica difícil de reviewar sin versión/Commitizen, README incompleto para réplica, y necesidad de validar el JSON cuantitativo **antes** de la IA.

Este change atiende ese feedback sin reabrir el split multi-repo ni features comerciales nuevas.

## Goals / Non-Goals

**Goals:**

- Higiene: un schemas home; clients solo `v0` en hot path; docs de middleware/assets.
- Versionar report PDF/job bajo `services/v0/reports/`.
- Abstracción LLM intercambiable (local sin AWS).
- Dump cuantitativo sin LLM (JSON obligatorio; Excel si cabe en el sprint).
- SemVer alineado + runbook README + checklist demo Swagger/PR.

**Non-Goals:**

- Sustituir Groq/Bedrock por un único vendor definitivo en prod (solo desacoplar).
- Producto “export Excel” vendible al cliente final.
- Refactor front/admin UI.
- Dividir la PR en N micros PRs obligatorias (Luis aceptó PR grande si está versionada y documentada).

## Decisions

### D1 — Eliminar shim `routers/auth_schemas.py`

- **Decisión:** Solo `app/schemas/auth_schemas.py`; actualizar imports; borrar shim.
- **Rationale:** Respuesta directa a “no sé en cuál meter la mano”.

### D2 — Shims flat `clients/*.py` fuera del hot path

- **Decisión:** Migrar imports restantes a `clients/v0`; eliminar flat o dejar stub que falle/deprecado y no se use.
- **Rationale:** Luis confundió Bedrock L63 vs L66; un solo árbol.

### D3 — Report services dentro de `services/v0/reports/`

- **Decisión:** Mover `report_pdf_service.py` y `report_job_service.py` a `services/v0/reports/`; actualizar imports.
- **Alternativa:** Dejar en raíz + doc — rechazada porque Luis pidió versionar lo que toca prod.
- **Rationale:** Misma frontera `v0` que analytics/payments/reports_service.

### D4 — LLM provider Adapter

- **Decisión:** Introducir facade/processed `clients/v0/llm/` (o renombrar rol de bedrock processed a “llm”) con `LLM_PROVIDER=groq|openai|bedrock`. Call sites de generación pasan por la facade; Bedrock es una impl.
- **Alternativa:** Solo documentar que hoy ya usamos Groq — insuficiente frente al amarre conceptual a Bedrock.
- **Rationale:** “No amarrar infraestructura con código”; OpenAI/Groq fáciles de licenciar para local.

### D5 — Debug cuantitativo

- **Decisión (mínimo viable):** Script CLI +/o endpoint interno `DEV_MODE`/rol admin que reutiliza `procesar_calculo_analitico` (o equivalente) y serializa JSON; flag `include_foda=false`.
- **Excel:** Incluir si el esfuerzo es bajo (`openpyxl` ya en admin); si no, JSON first y tarea Excel explícita.
- **Rationale:** “JSON sólido antes de la caja negra”.

### D6 — Versionado

- **Decisión:** Alinear a `1.0.0` (o `1.1.0` si `1.0.0` ya se usó simbólicamente) en `VERSION` + `pyproject.toml`; añadir sección Commitizen en README; opcional `cz.toml` mínimo.
- **Rationale:** Luis: esta línea de código = v1 robusta vs v0 previa.

### D7 — README + PR demo

- **Decisión:** Expandir README API; PR body con test plan Swagger (health, `/api/pagos/config`, previa mock si auth lo permite).
- **Rationale:** Réplica por Pedro/Luis/Miguel; demo sin front.

## Risks / Trade-offs

- **[Riesgo] Mover report_* rompe imports** → Mitigación: grep + suite pytest.
- **[Riesgo] Abstracción LLM más grande de lo esperado** → Mitigación: facade delgada sobre el camino Groq actual; Bedrock adapter stub/opcional.
- **[Riesgo] Endpoint debug expuesto** → Mitigación: solo `DEV_MODE` o auth admin; documentar.
- **[Trade-off] PR sigue siendo grande** → Aceptado por Luis; version + README + checklist compensan.

## Migration Plan

1. Higiene schemas/clients + docs middleware/assets.
2. Mover report services a `v0/reports`.
3. Facade LLM + config provider.
4. Dump JSON (y Excel si aplica).
5. SemVer + Commitizen docs + README.
6. PR + evidencia Swagger.

**Rollback:** revert de rama; sin migraciones BD.

## Resolved Questions (aprobación 27-jul-2026)

1. **Excel debug:** incluido en este change (junto con dump JSON).
2. **Env provider:** `LLM_PROVIDER` (valores: `groq` | `openai` | `bedrock`).
3. **SemVer:** alinear a **`1.0.0`** (`VERSION` + `pyproject.toml`).
