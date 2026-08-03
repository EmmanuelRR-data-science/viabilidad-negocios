#!/usr/bin/env bash
# Restaura agebs_demografia usando solo Docker (sin psql/pg_restore en el host).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
DUMP_FILE="${1:-${ROOT}/geo-viabilidad-api/backups/agebs_demografia.dump}"
CONTAINER="${GEO_DB_CONTAINER:-geo-analisis-db}"
DB_USER="${DB_USER:-admin}"
DB_NAME="${DB_NAME:-geoanalisis}"
DB_PASSWORD="${DB_PASSWORD:-admin_password_safe}"

if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "No se encontró el dump: ${DUMP_FILE}" >&2
  echo "Ejecuta: git lfs install && git lfs pull" >&2
  exit 1
fi

if ! docker inspect "${CONTAINER}" >/dev/null 2>&1; then
  echo "Contenedor ${CONTAINER} no existe. Levanta el stack: docker compose up -d" >&2
  exit 1
fi

echo "Esperando PostGIS healthy..."
for _ in $(seq 1 30); do
  if docker inspect -f '{{.State.Health.Status}}' "${CONTAINER}" 2>/dev/null | grep -q healthy; then
    break
  fi
  sleep 2
done

echo "Copiando dump al contenedor..."
docker cp "${DUMP_FILE}" "${CONTAINER}:/tmp/agebs_demografia.dump"

echo "Asegurando extensión PostGIS..."
docker exec -e PGPASSWORD="${DB_PASSWORD}" "${CONTAINER}" \
  psql -U "${DB_USER}" -d "${DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS postgis;"

echo "Restaurando dump..."
docker exec -e PGPASSWORD="${DB_PASSWORD}" "${CONTAINER}" \
  pg_restore \
  -U "${DB_USER}" \
  -d "${DB_NAME}" \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  /tmp/agebs_demografia.dump

echo "Verificando cobertura..."
docker exec -e PGPASSWORD="${DB_PASSWORD}" "${CONTAINER}" \
  psql -U "${DB_USER}" -d "${DB_NAME}" -c \
  "SELECT COUNT(*) AS total,
          COUNT(*) FILTER (WHERE geom IS NOT NULL) AS con_geom,
          COUNT(*) FILTER (WHERE graproes > 0) AS con_nse
   FROM agebs_demografia;"
docker exec -e PGPASSWORD="${DB_PASSWORD}" "${CONTAINER}" \
  psql -U "${DB_USER}" -d "${DB_NAME}" -c \
  "SELECT COUNT(*) AS categorias FROM categorias_cruce;"

docker exec "${CONTAINER}" rm -f /tmp/agebs_demografia.dump
echo "Restauración completada."
