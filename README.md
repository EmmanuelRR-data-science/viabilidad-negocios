# Geo Viabilidad Negocios

Monorepo del producto **GeoViabilidad**: análisis de viabilidad comercial geoespacial para México.

---

## Despliegue rápido tras `git clone`

### Opción A — un solo script

**Linux / macOS / WSL:**

```bash
git clone https://github.com/PhiQus-DS/pq-edm-viabilidad.git
cd pq-edm-viabilidad
git checkout PR-v1
chmod +x setup_local.sh
./setup_local.sh
```

**Windows (Git Bash / WSL):**

```bash
# Abre Git Bash (instalado con Git para Windows) o la terminal de WSL
git clone https://github.com/PhiQus-DS/pq-edm-viabilidad.git
cd pq-edm-viabilidad
git checkout PR-v1
chmod +x setup_local.sh
./setup_local.sh
```

`setup_local.sh` hace, en orden: copia `.env` si falta → `git lfs pull` (dump ~67 MB) → `docker compose build` + `up -d` → restaura `agebs_demografia` **dentro del contenedor PostGIS** (no necesitas `psql` en el host).

Comprueba:

```bash
curl http://localhost:8001/health
# → {"status":"online", ...}
```

| Servicio | URL |
|----------|-----|
| SPA | http://localhost:8000 |
| API / Swagger | http://localhost:8001/docs |
| Admin | http://localhost:8501/admin/login |
| Gate PhiQus | usuario `PhiQus` / contraseña `viabilidad-negocios` |

### Opción B — pasos manuales

```bash
git clone https://github.com/PhiQus-DS/pq-edm-viabilidad.git
cd pq-edm-viabilidad && git checkout PR-v1
cp .env.example .env && git lfs install && git lfs pull
./run_local.sh
bash geo-viabilidad-api/scripts/demografia/restore_demografia_docker.sh
```

En Windows: se recomienda usar Git Bash o WSL para ejecutar `./run_local.sh` y `./setup_local.sh` directamente, asegurando compatibilidad nativa con el stack Linux de contenedores.

> **Requisito:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) + [Git LFS](https://git-lfs.com/). La primera build puede tardar varios minutos (GDAL en la imagen API).

---

## Requisitos

| Herramienta | Para qué |
|-------------|----------|
| **Docker** + Compose v2 | Stack completo (PostGIS, API, SPA, Admin) |
| **bash** | `./run_local.sh` (Linux / macOS / WSL) |
| **uv** ([instalar](https://docs.astral.sh/uv/)) | Tests / desarrollo Python fuera de Docker |

Opcional para flujo “completo” en local: claves `GOOGLE_MAPS` / `GOOGLE_OAUTH`, `GROQ_API_KEY`. Con `PAYMENTS_MODE=mock` **no** hace falta Mercado Pago ni AWS.

> **Windows:** usa Git Bash o WSL con `./run_local.sh` y `./setup_local.sh` (mismo stack Linux que Docker).

---

## Mapa del monorepo

| Carpeta | Rol | Puerto local |
|---------|-----|--------------|
| `geo-viabilidad-web/` | SPA (HTML/CSS/JS) vía nginx | **8000** |
| `geo-viabilidad-api/` | Backend FastAPI + motor analítico | **8001** (Swagger/docs) |
| `geo-viabilidad-admin/` | Panel Flask (órdenes, leads, ingesta) | **8501** |
| `geo-viabilidad-data/` | Paquete compartido ORM / PostGIS / INEGI | librería (`uv`) |

Versiones de producto (SemVer):

- API / Admin / Web: ver `*/VERSION` (API alineada a **1.0.0**)
- Data: `geo-viabilidad-data/VERSION` (**0.1.0**)

---

## Arranque en 3 pasos

### 1. Variables de entorno

```bash
cd geo-viabilidad-negocios
cp .env.example .env
```

Valores **recomendados para local** (ya vienen en `.env.example`):

| Variable | Valor local | Nota |
|----------|-------------|------|
| `DEV_MODE` | `true` | Sin AWS obligatorio |
| `PAYMENTS_MODE` | `mock` | Checkout simulado (`mock` \| `sandbox` \| `live`) |
| `REPORTS_LOCAL_STORAGE` | `true` | PDF en disco |
| `LLM_PROVIDER` | `groq` | Alternativas: `openai`, `bedrock` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `PhiQus` / `viabilidad-negocios` | Gate SPA + Admin |

Para Places / OAuth / FODA con LLM, completa en `.env`:

- `GOOGLE_PLACES_API_KEY` o `GOOGLE_MAPS_API_KEY`
- `GOOGLE_OAUTH_CLIENT_ID` (login Google en la SPA)
- `GROQ_API_KEY` (si `LLM_PROVIDER=groq`)

### 2. Levantar el stack

```bash
chmod +x run_local.sh   # solo la primera vez
./run_local.sh
```

Eso hace `docker compose build` + `up -d` (PostGIS, API, SPA, Admin).  
La primera vez puede tardar varios minutos (build de imágenes + GDAL).

### 3. Abrir y comprobar

| Qué | URL |
|-----|-----|
| **App (SPA)** | http://localhost:8000 |
| **Swagger / OpenAPI** | http://localhost:8001/docs |
| **Health API** | http://localhost:8001/health |
| **Admin** | http://localhost:8501/admin/login |

**Puerta PhiQus** (SPA y Admin):

| Campo | Valor |
|-------|-------|
| Usuario | `PhiQus` |
| Contraseña | `viabilidad-negocios` |

Smoke rápido:

```bash
curl http://localhost:8001/health
# → JSON con "status": "online" (HTTP 200)
```

En Swagger: `GET /api/pagos/config` (con mock no exige MP real).

---

## Datos demográficos (primera vez / BD vacía)

Sin tablas censales el análisis cuantitativo no tiene población/NSE reales.

Con el stack arriba (`geo-db` healthy):

```bash
# Solo Docker (sin psql en el host) — recomendado
bash geo-viabilidad-api/scripts/demografia/restore_demografia_docker.sh

# Alternativa si ya tienes psql/pg_restore instalados en el host
bash geo-viabilidad-api/scripts/demografia/restore_demografia_local.sh
```

Detalle de scripts: [`geo-viabilidad-api/scripts/README.md`](geo-viabilidad-api/scripts/README.md).

---

## Flujo de prueba sugerido

1. http://localhost:8000 → login PhiQus.
2. Marcar un punto en CDMX, elegir giro (ej. Cafetería), **Analizar**.
3. Con `PAYMENTS_MODE=mock`, comprar un plan y validar que el PDF se genera / descarga.
4. Alternativa solo API: usar Swagger en `:8001/docs` (health, pagos/config, endpoints de análisis según contrato).


