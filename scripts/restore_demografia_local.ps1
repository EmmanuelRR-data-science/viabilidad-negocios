# Restaura el respaldo nacional en PostGIS local (puerto 5435 por defecto).
param(
    [string]$DumpFile = (Join-Path (Split-Path -Parent $PSScriptRoot) "backups\agebs_demografia.dump")
)

$ErrorActionPreference = "Stop"
$env:DB_HOST = if ($env:DB_HOST) { $env:DB_HOST } else { "127.0.0.1" }
$env:DB_PORT = if ($env:DB_PORT) { $env:DB_PORT } else { "5435" }
$env:DB_USER = if ($env:DB_USER) { $env:DB_USER } else { "admin" }
$env:DB_NAME = if ($env:DB_NAME) { $env:DB_NAME } else { "geoanalisis" }
$env:DB_PASSWORD = if ($env:DB_PASSWORD) { $env:DB_PASSWORD } else { "admin_password_safe" }

if (-not (Test-Path $DumpFile)) {
    throw "No se encontró el dump: $DumpFile"
}

Write-Host "Restaurando $DumpFile en $($env:DB_HOST):$($env:DB_PORT)..."
bash (Join-Path $PSScriptRoot "restore_demografia_local.sh") $DumpFile.Replace("\", "/")
