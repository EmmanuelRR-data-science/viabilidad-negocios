#!/usr/bin/env bash
# =====================================================================
# GeoViabilidad Hook - Script de Inicialización Local (Shell)
# =====================================================================

set -e

echo "========================================================="
echo "🚀 Iniciando Entorno Dockerizado de GeoViabilidad Hook 🚀"
echo "========================================================="

# 1. Verificar existencia de .env
if [ ! -f .env ]; then
    echo "⚠️ .env no encontrado. Copiando .env.example..."
    cp .env.example .env
fi

# 2. Compilar e iniciar los servicios con Docker Compose
echo "🛠️ Compilando imágenes Docker locales..."
docker compose build

echo "🚦 Levantando servicios (Streamlit en 8501, FastAPI en 8000)..."
docker compose up -d

echo "========================================================="
echo "🎉 ¡SERVICIOS INICIADOS CORRECTAMENTE! 🎉"
echo "========================================================="
echo "👉 Panel de Administración (Streamlit): http://localhost:8501"
echo "👉 API y SPA Público (FastAPI + SPA): http://localhost:8000"
echo "👉 Documentación Interactiva OpenAPI:  http://localhost:8000/docs"
echo "========================================================="
echo "Para ver los logs en tiempo real ejecute: docker compose logs -f"
