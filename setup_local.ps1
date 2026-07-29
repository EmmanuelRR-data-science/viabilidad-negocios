# Clone -> deploy -> datos demograficos (Windows PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host " Geo Viabilidad - setup local completo" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Write-Host ".env no encontrado. Copiando .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

if (-not (Get-Command git-lfs -ErrorAction SilentlyContinue)) {
    Write-Error "Git LFS no esta instalado. Instalo para descargar el dump demografico."
}

Write-Host "Descargando dump demografico (Git LFS)..." -ForegroundColor Green
git lfs install --local 2>$null
git lfs pull
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Compilando y levantando contenedores..." -ForegroundColor Green
docker compose build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker compose up -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Restaurando base demografica (Docker)..." -ForegroundColor Green
$dumpPath = Join-Path $PWD "geo-viabilidad-api/backups/agebs_demografia.dump"
$container = "geo-analisis-db"
$dbUser = if ($env:DB_USER) { $env:DB_USER } else { "admin" }
$dbName = if ($env:DB_NAME) { $env:DB_NAME } else { "geoanalisis" }
$dbPassword = if ($env:DB_PASSWORD) { $env:DB_PASSWORD } else { "admin_password_safe" }

if (-not (Test-Path $dumpPath)) {
    Write-Error "No se encontro el dump: $dumpPath. Ejecuta: git lfs pull"
}

Write-Host "Esperando PostGIS healthy..." -ForegroundColor Yellow
for ($i = 0; $i -lt 30; $i++) {
    $status = docker inspect -f '{{.State.Health.Status}}' $container 2>$null
    if ($status -eq "healthy") { break }
    Start-Sleep -Seconds 2
}

docker cp $dumpPath ($container + ":/tmp/agebs_demografia.dump")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker exec -e "PGPASSWORD=$dbPassword" $container psql -U $dbUser -d $dbName -c "CREATE EXTENSION IF NOT EXISTS postgis;"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker exec -e "PGPASSWORD=$dbPassword" $container pg_restore -U $dbUser -d $dbName --clean --if-exists --no-owner --no-acl /tmp/agebs_demografia.dump
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker exec -e "PGPASSWORD=$dbPassword" $container psql -U $dbUser -d $dbName -c "SELECT COUNT(*) AS total FROM agebs_demografia;"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker exec $container rm -f /tmp/agebs_demografia.dump
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host " Listo" -ForegroundColor Green
Write-Host " SPA:    http://localhost:8000" -ForegroundColor Yellow
Write-Host " API:    http://localhost:8001/docs" -ForegroundColor Yellow
Write-Host " Health: http://localhost:8001/health" -ForegroundColor Yellow
Write-Host " Admin:  http://localhost:8501/admin/login" -ForegroundColor Yellow
Write-Host " Gate:   usuario PhiQus / viabilidad-negocios" -ForegroundColor Yellow
Write-Host "=========================================================" -ForegroundColor Cyan
