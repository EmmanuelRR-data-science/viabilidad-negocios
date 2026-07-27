# Geo Viabilidad Negocios — levantar stack local
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host " Geo Viabilidad Negocios — Docker Compose" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Write-Host ".env no encontrado. Copiando .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

Write-Host "Compilando imágenes..." -ForegroundColor Green
docker compose build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Levantando PostGIS, SPA (8000), API (8001) y Admin (8501)..." -ForegroundColor Green
docker compose up -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host " Listo" -ForegroundColor Green
Write-Host " SPA:    http://localhost:8000" -ForegroundColor Yellow
Write-Host " API:    http://localhost:8001/docs" -ForegroundColor Yellow
Write-Host " Health: http://localhost:8001/health" -ForegroundColor Yellow
Write-Host " Admin:  http://localhost:8501/admin/login" -ForegroundColor Yellow
Write-Host " Gate:   usuario PhiQus / viabilidad-negocios" -ForegroundColor Yellow
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host " Runbook completo: README.md (raiz del monorepo)" -ForegroundColor Cyan
Write-Host " En Linux/macOS/WSL usa: ./run_local.sh" -ForegroundColor Cyan
