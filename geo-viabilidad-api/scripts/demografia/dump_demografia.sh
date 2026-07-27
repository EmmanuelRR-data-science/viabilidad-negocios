#!/usr/bin/env bash
# Exporta la tabla agebs_demografia (PostGIS) para replicar en VPS.
set -euo pipefail

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5435}"
DB_USER="${DB_USER:-admin}"
DB_NAME="${DB_NAME:-geoanalisis}"
OUT_FILE="${1:-agebs_demografia.dump}"

export PGPASSWORD="${DB_PASSWORD:-admin_password_safe}"

echo "Exportando agebs_demografia -> ${OUT_FILE}"
pg_dump \
  -h "${DB_HOST}" \
  -p "${DB_PORT}" \
  -U "${DB_USER}" \
  -d "${DB_NAME}" \
  -Fc \
  --no-owner \
  --no-acl \
  -t agebs_demografia \
  -f "${OUT_FILE}"

echo "Listo: $(du -h "${OUT_FILE}" | cut -f1)"
