# Geo Viabilidad — API

Backend FastAPI: motor analítico (PostGIS/INEGI), pagos (Mercado Pago), reportes PDF, integraciones externas.

**Versión de código:** `1.0.0` (alineada en `VERSION` y `pyproject.toml`).

Arquitectura por capas: [`rfcs/rfc-api-layers.md`](../rfcs/rfc-api-layers.md) · monorepo: [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

---

## Arranque rápido

Desde la raíz del monorepo (`geo-viabilidad-negocios/`):

```bash
./run_local.sh      # build + up (Linux / macOS / WSL / Git Bash)
./setup_local.sh    # incluye restore del dump demográfico
```

Eso levanta (típico) PostGIS, API y web vía Docker Compose.

| Qué | URL |
|-----|-----|
| Swagger / OpenAPI UI | http://localhost:8001/docs |
| OpenAPI JSON | http://localhost:8001/api/openapi.json |
| Health | http://localhost:8001/health |
| SPA (nginx) | http://localhost:8000 |

### Variables mínimas (`.env` en raíz o API)

| Variable | Uso |
|----------|-----|
| `DEV_MODE` | `true` en local (Groq / mocks de AWS) |
| `PAYMENTS_MODE` | `mock` \| `sandbox` \| `live` — modo de cobro (config de despliegue) |
| `REPORTS_LOCAL_STORAGE` | `true` → PDF en `scratch/reports` |
| `LLM_PROVIDER` | `groq` \| `openai` \| `bedrock` (default: `groq`) |
| `GROQ_API_KEY` | Clave de API Groq (desarrollo local) |
| `OPENAI_API_KEY` | Clave de API OpenAI (alternativa a Groq) |
| `OPENAI_MODEL` | Modelo OpenAI (default: `gpt-4o-mini`) |
| `GOOGLE_MAPS_API_KEY` | Places / geocoding |
| Credenciales DB | vía compose / `geo-viabilidad-data` |

Copia desde `.env.example` en la raíz del monorepo.

### API sola (sin compose)

```powershell
cd geo-viabilidad-api
uv sync --group dev
$env:PYTHONPATH = (Get-Location).Path
uv run uvicorn app.main:app --reload --port 8001
```

`geo-viabilidad-data` se instala vía path editable (`[tool.uv.sources]` en `pyproject.toml`).

### Calidad (Ruff)

```powershell
uv run ruff check app tests scripts
uv run ruff format app tests scripts
```

---

## Estructura (`app/`)

```
app/
  main.py           # wiring + handler UserFacingError + /health
  core/             # config, middleware (errores user-centric + rate-limit LLM), security
  exceptions/       # UserFacingError y subtipos
  routers/          # HTTP delgado (auth, v0/analytics|payments|reports)
  services/         # orquestación; presentation/, assets/ (logos PDF), tiers/, v0/
    v0/
      analytics/    # motor analítico cuantitativo
      payments/     # Mercado Pago checkout + webhooks
      reports/      # report_pdf_service, report_job_service, reports_service
  domain/           # reglas puras (sin SQL/HTTP)
  clients/v0/       # raw+processed: google, bedrock, llm, besttime, mp, s3, ses, tiles, database
  schemas/          # DTOs (incl. auth_schemas) — único home de schemas
```

### Middleware real (no solo nombre de carpeta)

- `UserFriendlyExceptionMiddleware` — traduce fallos de infra a mensajes amigables
- `LLMRateLimitMiddleware` — límite por IP en rutas LLM sensibles
- Handler FastAPI de `UserFacingError` en `main.py`

### `services/assets/`

Imágenes de portada/logo para el PDF generado por ReportLab. Es un módulo de datos dentro de services, no una capa arquitectónica.

### `LLM_PROVIDER`

La variable de entorno `LLM_PROVIDER` (valores: `groq` | `openai` | `bedrock`) selecciona el backend de IA para generación FODA.

- **groq** (default): HTTP a Groq API — funciona en local sin AWS.
- **openai**: HTTP a OpenAI chat completions — alternativa local.
- **bedrock**: AWS Bedrock Runtime — producción con IAM configurado.

La facade vive en `app/clients/v0/llm/` con un adapter por provider.

Detalle: `../rfcs/rfc-api-layers.md`.

---

## Tests

```powershell
cd geo-viabilidad-api
$env:PYTHONPATH = (Get-Location).Path
uv run pytest tests/ -q
```

Incluye `tests/test_architecture_layers.py` (fronteras routers/domain/clients) y `tests/test_llm_provider.py` (registry + mocks).

---

## Debug cuantitativo (sin IA)

Para inspeccionar el JSON del motor (demografía, NSE, competencia, scores) **sin** llamar al LLM:

```powershell
cd geo-viabilidad-api
$env:PYTHONPATH = (Get-Location).Path
uv run python scripts/debug_analisis_cuantitativo.py --lat 19.43 --lng -99.13 --radio 1000 --rubro cafeteria --excel
```

Genera archivos en `scratch/`:
- `debug_cuantitativo_<ts>.json` — payload completo del motor cuantitativo
- `debug_cuantitativo_<ts>.xlsx` — hojas: KPIs, NSE, Competidores, Aliados, Afluencia, Segmentación

También existe endpoint interno en `DEV_MODE`:

```
GET /api/analizar/debug/cuantitativo?lat=19.43&lng=-99.13&radio_metros=1000&rubro=cafeteria
```

**No** sustituye ni bypassa el PDF pagado.

---

## Versionado (SemVer + Commitizen)

Fuentes de verdad alineadas a **`1.0.0`**:

- `VERSION`
- `pyproject.toml` → `[project].version`

**Política de versiones:**
- Cambios aditivos dentro de `v0/` → patch/minor bump
- Cambios que rompen contratos HTTP existentes → nuevo paquete de versión (e.g. `v1/`)

Bump manual: editar `VERSION` y `pyproject.toml` al mismo valor.

Con [Commitizen](https://commitizen-tools.github.io/commitizen/) (opcional):

```powershell
uv tool install commitizen
cz bump --increment PATCH   # o MINOR / MAJOR
```

La sección `[tool.commitizen]` en `pyproject.toml` configura `version_files` para mantener `VERSION` y `pyproject.toml` sincronizados automáticamente al ejecutar `cz bump`.

---

## Scripts operativos

Ver `scripts/README.md` (ingesta INEGI, demografía dump/restore en WSL).

```bash
bash scripts/demografia/restore_demografia_local.sh
```

---

## Demo Swagger (sin front)

1. Abrir http://localhost:8001/docs
2. `GET /health` → `status: online`
3. `GET /api/pagos/config` → configuración de pagos (mock o live)
4. Flujos `/api/analizar/*` y `/api/pagos/*` con auth Google mock según `DEV_MODE`
5. `GET /api/analizar/debug/cuantitativo?lat=19.43&lng=-99.13` → JSON cuantitativo (solo DEV_MODE)
