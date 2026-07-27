#!/usr/bin/env bash
# Sincroniza agebs_demografia local -> VPS vía pg_dump / scp / pg_restore.
# Ejecutar desde WSL o Linux/macOS (no PowerShell).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VPS_HOST="${VPS_HOST:-root@135.181.30.179}"
VPS_PATH="${VPS_PATH:-/opt/viabilidad-negocios}"
DUMP_FILE="${DUMP_FILE:-agebs_demografia.dump}"
DUMP_PATH="${API_ROOT}/${DUMP_FILE}"

export DB_HOST="${DB_HOST:-127.0.0.1}"
export DB_PORT="${DB_PORT:-5435}"
export DB_USER="${DB_USER:-admin}"
export DB_NAME="${DB_NAME:-geoanalisis}"
export DB_PASSWORD="${DB_PASSWORD:-admin_password_safe}"

echo "1/4 Exportando tabla local..."
bash "${SCRIPT_DIR}/dump_demografia.sh" "${DUMP_PATH}"

echo "2/4 Subiendo dump al VPS..."
scp "${DUMP_PATH}" "${VPS_HOST}:${VPS_PATH}/${DUMP_FILE}"

echo "3/4 Restaurando en VPS..."
ssh "${VPS_HOST}" "cd ${VPS_PATH} && set -a && source .env 2>/dev/null || true && set +a && export DB_HOST=\${DB_HOST:-localhost} && bash scripts/demografia/restore_demografia_vps.sh ${DUMP_FILE}"

echo "4/4 Limpieza local del dump temporal..."
rm -f "${DUMP_PATH}"
echo "Sincronización completada."
