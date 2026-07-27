#!/usr/bin/env bash
# Restaura agebs_demografia en el VPS (reemplaza datos existentes).
set -euo pipefail

DUMP_FILE="${1:-agebs_demografia.dump}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-admin}"
DB_NAME="${DB_NAME:-geoanalisis}"

export PGPASSWORD="${DB_PASSWORD:?Definir DB_PASSWORD}"

echo "Asegurando esquema PostGIS..."
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS postgis;"

echo "Restaurando ${DUMP_FILE} (modo --clean --if-exists)..."
pg_restore \
  -h "${DB_HOST}" \
  -p "${DB_PORT}" \
  -U "${DB_USER}" \
  -d "${DB_NAME}" \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  "${DUMP_FILE}"

echo "Verificando cobertura NSE..."
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c \
  "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE graproes > 0) AS con_nse FROM agebs_demografia;"
