# Scripts operativos (`geo-viabilidad-api/scripts`)

CLIs de **servidor**. No son endpoints HTTP ni parte de la API pública del usuario.

## Convención

- Ejecutar en **Linux/macOS** o **WSL en Windows** (shell `.sh` + Python).
- No hay scripts `.ps1` duplicados en esta carpeta.
- Scripts de hardening/VPS **no viven aquí** (otro repo / operaciones).

### Windows + WSL

```powershell
# Abrir shell Linux del repo (una vez instalado WSL)
wsl
cd /mnt/c/Users/<tu-usuario>/OneDrive\ -\ PhiQus/Escritorio/geo-viabilidad-negocios/geo-viabilidad-api
```

Desde ahí ejecuta los `.sh` y los `python scripts/...` como en Linux.

## Inventario

### `ingest_inegi/`

| Script | Qué hace |
|--------|----------|
| `ingest_all_states.py` | Ingesta nacional INEGI (32 estados) vía `geo_viabilidad_data` |
| `ingest_censo_nse.py` | Actualiza variables censales / NSE sin shapefiles |

```bash
python scripts/ingest_inegi/ingest_all_states.py
python scripts/ingest_inegi/ingest_censo_nse.py
```

### `demografia/`

| Script | Qué hace |
|--------|----------|
| `dump_demografia.sh` | Exporta dump de tablas demográficas |
| `restore_demografia_local.sh` | Restaura PostGIS local desde dump |
| `restore_demografia_vps.sh` | Restaura demografía en entorno remoto (ops) |
| `sync_demografia_vps.sh` | Dump local → scp → restore en VPS |

```bash
bash scripts/demografia/restore_demografia_local.sh
# opcional: bash scripts/demografia/sync_demografia_vps.sh
```

### Raíz de `scripts/`

| Script | Qué hace |
|--------|----------|
| `benchmark_metricas.py` | Benchmark de latencias HTTP + PostGIS + flujo post-pago/PDF (salida: `benchmark_metricas_result.json`) |
| `migrate_aliados_guiados.py` | Migración one-off de config aliados guiados |

```bash
# Ejemplo (API arriba en :8001):
PYTHONPATH=. uv run python scripts/benchmark_metricas.py --base-url http://localhost:8001
```
