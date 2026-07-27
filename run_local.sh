#!/usr/bin/env bash
# Geo Viabilidad Negocios â€” levantar stack local (Linux / macOS / WSL)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "========================================================="
echo " Geo Viabilidad Negocios â€” Docker Compose"
echo "========================================================="

if [[ ! -f .env ]]; then
  echo ".env no encontrado. Copiando .env.example..."
  cp .env.example .env
fi

echo "Compilando imÃ¡genes..."
docker compose build

echo "Levantando PostGIS, SPA (8000), API (8001) y Admin (8501)..."
docker compose up -d

echo "========================================================="
echo " Listo"
echo " SPA:    http://localhost:8000"
echo " API:    http://localhost:8001/docs"
echo " Health: http://localhost:8001/health"
echo " Admin:  http://localhost:8501/admin/login"
echo " Gate:   usuario PhiQus / viabilidad-negocios"
echo "========================================================="
echo " Runbook completo: README.md (raiz del monorepo)"
