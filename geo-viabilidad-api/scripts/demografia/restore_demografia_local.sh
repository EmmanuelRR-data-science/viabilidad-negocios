#!/usr/bin/env bash
# Restaura el respaldo nacional (agebs_demografia + categorias_cruce) en PostGIS local.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DUMP_FILE="${1:-${ROOT}/backups/agebs_demografia.dump}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5435}"
DB_USER="${DB_USER:-admin}"
DB_NAME="${DB_NAME:-geoanalisis}"

export PGPASSWORD="${DB_PASSWORD:-admin_password_safe}"

if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "No se encontró el dump: ${DUMP_FILE}" >&2
  exit 1
fi

echo "Asegurando PostGIS en ${DB_HOST}:${DB_PORT}/${DB_NAME}..."
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
  -c "CREATE EXTENSION IF NOT EXISTS postgis;"

echo "Restaurando ${DUMP_FILE}..."
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

echo "Verificando cobertura..."
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c \
  "SELECT COUNT(*) AS total,
          COUNT(*) FILTER (WHERE geom IS NOT NULL) AS con_geom,
          COUNT(*) FILTER (WHERE graproes > 0) AS con_nse
   FROM agebs_demografia;"
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c \
  "SELECT COUNT(*) AS categorias FROM categorias_cruce;"

echo "Restauración completada."
