# Sincroniza agebs_demografia local -> VPS vía pg_dump / scp / pg_restore.
param(
    [string]$VpsHost = "root@135.181.30.179",
    [string]$VpsPath = "/opt/viabilidad-negocios",
    [string]$DumpFile = "agebs_demografia.dump"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$DumpPath = Join-Path $Root $DumpFile

$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "5435"
$env:DB_USER = "admin"
$env:DB_NAME = "geoanalisis"
$env:DB_PASSWORD = "admin_password_safe"

Write-Host "1/4 Exportando tabla local..."
bash "$Root/scripts/dump_demografia.sh" "$DumpPath"

Write-Host "2/4 Subiendo dump al VPS..."
scp $DumpPath "${VpsHost}:${VpsPath}/${DumpFile}"

Write-Host "3/4 Restaurando en VPS..."
ssh $VpsHost @"
cd $VpsPath
set -a && source .env 2>/dev/null || true && set +a
export DB_HOST=\${DB_HOST:-localhost}
bash scripts/restore_demografia_vps.sh $DumpFile
"@

Write-Host "4/4 Limpieza local del dump temporal..."
Remove-Item $DumpPath -Force -ErrorAction SilentlyContinue
Write-Host "Sincronización completada."
