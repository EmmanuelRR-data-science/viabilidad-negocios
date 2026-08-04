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

echo "Compilando imágenes..."
docker compose build

echo "Levantando PostGIS, SPA (8000), API (8001) y Admin (8501)..."
docker compose up -d

echo "========================================================="
echo " Listo - Se ha intentado levantar el stack de Docker"
echo " Ejecuta 'docker compose ps' para verificar el estado de los servicios."
echo " Datos demográficos (primera vez): ./setup_local.sh"
echo " Runbook completo y puertos por defecto: README.md"
echo "========================================================="
