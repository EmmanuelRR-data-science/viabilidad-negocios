# =====================================================================
# GeoViabilidad Hook - Script de Inicialización Local (PowerShell)
# =====================================================================

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "🚀 Iniciando Entorno Dockerizado de GeoViabilidad Hook 🚀" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

# 1. Verificar existencia de .env
if (-not (Test-Path ".env")) {
    Write-Host "⚠️ .env no encontrado. Copiando .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

# 2. Compilar e iniciar los servicios con Docker Compose
Write-Host "🛠️ Compilando imágenes Docker locales..." -ForegroundColor Green
docker compose build

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Falla al compilar las imágenes Docker." -ForegroundColor Red
    Exit $LASTEXITCODE
}

Write-Host "🚦 Levantando servicios (Streamlit en 8501, FastAPI en 8000)..." -ForegroundColor Green
docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Falla al levantar los contenedores con docker compose." -ForegroundColor Red
    Exit $LASTEXITCODE
}

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "🎉 ¡SERVICIOS INICIADOS CORRECTAMENTE! 🎉" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "👉 Panel de Administración (Streamlit): http://localhost:8501" -ForegroundColor Yellow
Write-Host "👉 API y SPA Público (FastAPI + SPA): http://localhost:8000" -ForegroundColor Yellow
Write-Host "👉 Documentación Interactiva OpenAPI:  http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "Para ver los logs en tiempo real ejecute: docker compose logs -f" -ForegroundColor White
