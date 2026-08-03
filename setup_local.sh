#!/usr/bin/env bash
# Clone → deploy → datos demográficos en un solo script (Linux / macOS / WSL).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "========================================================="
echo " Geo Viabilidad — setup local completo"
echo "========================================================="

if [[ ! -f .env ]]; then
  echo ".env no encontrado. Copiando .env.example..."
  cp .env.example .env
fi

if ! command -v git-lfs >/dev/null 2>&1; then
  echo "Git LFS no está instalado. Instálalo para descargar el dump demográfico." >&2
  exit 1
fi

echo "Descargando dump demográfico (Git LFS)..."
git lfs install --local >/dev/null 2>&1 || true
git lfs pull

echo "Compilando y levantando contenedores..."
docker compose build
docker compose up -d

echo "Restaurando base demográfica..."
bash "${ROOT}/geo-viabilidad-api/scripts/demografia/restore_demografia_docker.sh"

echo "========================================================="
echo " Listo"
echo " SPA:    http://localhost:8000"
echo " API:    http://localhost:8001/docs"
echo " Health: http://localhost:8001/health"
echo " Admin:  http://localhost:8501/admin/login"
echo " Gate:   usuario PhiQus / viabilidad-negocios"
echo "========================================================="
