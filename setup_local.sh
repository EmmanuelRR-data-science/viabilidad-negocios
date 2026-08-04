#!/usr/bin/env bash
# Clone -> deploy -> datos demograficos (Bash / Linux compatible)
set -e

# Códigos de escape ANSI para colores en consola
CYAN='\e[36m'
YELLOW='\e[33m'
GREEN='\e[32m'
RED='\e[31m'
RESET='\e[0m'

echo -e "${CYAN}=========================================================${RESET}"
echo -e "${CYAN} Geo Viabilidad - setup local completo${RESET}"
echo -e "${CYAN}=========================================================${RESET}"

# Validar y copiar .env si no existe
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}.env no encontrado. Copiando .env.example...${RESET}"
    cp .env.example .env
fi

# Validar que git-lfs esté disponible
if ! command -v git-lfs &> /dev/null; then
    echo -e "${RED}Error: Git LFS no está instalado. Instálalo para descargar el dump demográfico.${RESET}"
    exit 1
fi

echo -e "${GREEN}Descargando dump demográfico (Git LFS)...${RESET}"
git lfs install --local 2>/dev/null || true
git lfs pull

# Cargar variables de entorno de .env para base de datos si existen
if [ -f ".env" ]; then
    # Exporta de forma segura evitando comentarios y líneas vacías
    export $(grep -v '^#' .env | xargs) 2>/dev/null || true
fi

# Asignar fallbacks a credenciales si no están definidas
DB_USER=${DB_USER:-"admin"}
DB_NAME=${DB_NAME:-"geoanalisis"}
DB_PASSWORD=${DB_PASSWORD:-"admin_password_safe"}
CONTAINER="geo-analisis-db"
DUMP_PATH="$(pwd)/geo-viabilidad-api/backups/agebs_demografia.dump"

if [ ! -f "$DUMP_PATH" ]; then
    echo -e "${RED}Error: No se encontró el dump: $DUMP_PATH. Ejecuta: git lfs pull${RESET}"
    exit 1
fi

echo -e "${GREEN}Compilando y levantando contenedores...${RESET}"
docker compose build
docker compose up -d

echo -e "${YELLOW}Esperando PostGIS healthy...${RESET}"
for i in {1..30}; do
    status=$(docker inspect -f '{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || true)
    if [ "$status" = "healthy" ]; then
        echo -e "${GREEN}¡PostGIS está listo!${RESET}"
        break
    fi
    sleep 2
done

# Restaurar base demográfica
echo -e "${GREEN}Copiando dump demográfico al contenedor...${RESET}"
docker cp "$DUMP_PATH" "$CONTAINER:/tmp/agebs_demografia.dump"

echo -e "${GREEN}Verificando/Creando extensión PostGIS...${RESET}"
docker exec -e "PGPASSWORD=$DB_PASSWORD" "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS postgis;"

echo -e "${GREEN}Restaurando base demográfica (pg_restore)...${RESET}"
docker exec -e "PGPASSWORD=$DB_PASSWORD" "$CONTAINER" pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner --no-acl /tmp/agebs_demografia.dump

echo -e "${GREEN}Validando datos cargados...${RESET}"
docker exec -e "PGPASSWORD=$DB_PASSWORD" "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT COUNT(*) AS total FROM agebs_demografia;"

echo -e "${GREEN}Limpiando contenedor...${RESET}"
docker exec "$CONTAINER" rm -f /tmp/agebs_demografia.dump

echo -e "${CYAN}=========================================================${RESET}"
echo -e " ${GREEN}Listo - Setup local y restauración completada${RESET}"
echo -e " Ejecuta 'docker compose ps' para validar puertos y estado de los servicios."
echo -e " Runbook completo y puertos de acceso en: README.md"
echo -e "${CYAN}=========================================================${RESET}"
