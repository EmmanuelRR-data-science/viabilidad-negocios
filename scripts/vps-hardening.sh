#!/usr/bin/env bash
# Endurecimiento del VPS: firewall + aislamiento de DB + solo frontends públicos.
# Puertos públicos: 22 (SSH limit), 8000 (GeoViabilidad), 3000 (AEDMI vía nginx).
# Admin / herramientas internas: 127.0.0.1 (túnel SSH).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log() { echo "[vps-hardening] $*"; }

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Ejecutar como root." >&2
    exit 1
  fi
}

install_nginx() {
  if ! command -v nginx >/dev/null 2>&1; then
    log "Instalando nginx..."
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx
  fi
  install -m 644 "${REPO_ROOT}/infra/vps/nginx-aedmi-frontend-proxy.conf" \
    /etc/nginx/sites-available/aedmi-frontend-proxy
  ln -sf /etc/nginx/sites-available/aedmi-frontend-proxy /etc/nginx/sites-enabled/aedmi-frontend-proxy
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable nginx
  systemctl restart nginx
}

patch_viabilidad_compose() {
  local compose="/opt/viabilidad-negocios/docker-compose.yml"
  [[ -f "${compose}" ]] || return 0
  log "Restringiendo admin Streamlit a localhost en viabilidad..."
  sed -i 's/"8501:8501"/"127.0.0.1:8501:8501"/' "${compose}"
  sed -i 's|geoanalisis-sdd_geo-network|geo-analisis_geo-network|g' "${compose}"
}

patch_aedmi_compose() {
  local compose="/root/aedmi/docker-compose.prod.yml"
  [[ -f "${compose}" ]] || return 0
  log "Restringiendo API AEDMI y moviendo frontend a puerto interno 3001..."
  sed -i 's|"${API_PORT:-8080}:8080"|"127.0.0.1:${API_PORT:-8080}:8080"|' "${compose}"
  sed -i 's|"${FRONTEND_PORT:-3000}:3000"|"127.0.0.1:3001:3000"|' "${compose}"
  if [[ -f /root/aedmi/.env.prod ]]; then
    sed -i 's|API_URL=http://135.181.30.179:8080|API_URL=http://135.181.30.179:3000|' /root/aedmi/.env.prod
    sed -i 's|NEXT_PUBLIC_API_URL=http://localhost:8080|NEXT_PUBLIC_API_URL=http://135.181.30.179:3000|' /root/aedmi/.env.prod
  fi
}

patch_cfe_compose() {
  local compose="/opt/cfe-dashboard/docker-compose.yml"
  [[ -f "${compose}" ]] || return 0
  log "Restringiendo CFE dashboard a localhost..."
  sed -i 's/"5050:5000"/"127.0.0.1:5050:5000"/' "${compose}"
}

ensure_geo_db_internal() {
  local compose="/opt/geo-analisis/docker-compose.yml"
  [[ -f "${compose}" ]] || return 0
  if ! grep -q 'internal: true' "${compose}"; then
    log "Marcando red geo-network como internal (sin salida a internet para DB)..."
    sed -i '/geo-network:/a\    internal: true' "${compose}"
    docker network rm geo-analisis_geo-network 2>/dev/null || true
    (cd /opt/geo-analisis && docker compose up -d)
  fi
}

apply_docker_user_rules() {
  local marker="# BEGIN VPS-HARDENING DOCKER-USER"
  local rules_file="/etc/ufw/after.rules"
  if grep -q "${marker}" "${rules_file}" 2>/dev/null; then
    log "Reglas DOCKER-USER ya aplicadas."
    return 0
  fi
  log "Integrando reglas DOCKER-USER en UFW..."
  cat >> "${rules_file}" <<'EOF'

# BEGIN VPS-HARDENING DOCKER-USER
*filter
:DOCKER-USER - [0:0]
-A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
-A DOCKER-USER -i lo -j RETURN
-A DOCKER-USER -s 10.0.0.0/8 -j RETURN
-A DOCKER-USER -s 172.16.0.0/12 -j RETURN
-A DOCKER-USER -s 192.168.0.0/16 -j RETURN
-A DOCKER-USER -p tcp -m multiport --dports 8501,5050,8080,5432 -j DROP
-A DOCKER-USER -j RETURN
COMMIT
# END VPS-HARDENING DOCKER-USER
EOF
  ufw reload || true
}

configure_ufw() {
  log "Reconfigurando UFW (solo frontends + SSH)..."
  ufw --force default deny incoming
  ufw --force default allow outgoing

  # Garantizar SSH ANTES de eliminar reglas antiguas
  ufw allow OpenSSH
  ufw limit OpenSSH

  # Eliminar solo reglas inseguras (no borrar todo el perfil)
  while ufw status numbered | grep -qE '\[(.*)\].*(5432|5050/tcp.*Anywhere|8501|8080)'; do
    num="$(ufw status numbered | grep -E '5432|5050/tcp.*Anywhere|8501|8080' | head -1 | sed -n 's/^\[\([0-9]*\)\].*/\1/p')"
    [[ -n "${num}" ]] && ufw --force delete "${num}" || break
  done

  ufw allow 8000/tcp comment 'GeoViabilidad frontend+API'
  ufw allow 3000/tcp comment 'AEDMI frontend (nginx proxy)'
  ufw allow 80/tcp comment 'HTTP reservado'
  ufw allow 443/tcp comment 'HTTPS reservado'

  for ip in 45.148.10.240 2.57.122.238 45.148.10.183 2.57.122.177 195.178.110.30; do
    ufw deny from "${ip}" 2>/dev/null || true
  done

  ufw --force enable
}

restart_stacks() {
  log "Reiniciando stacks..."
  (cd /opt/viabilidad-negocios && docker compose up -d)
  (cd /root/aedmi && docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build frontend)
  (cd /opt/cfe-dashboard && docker compose up -d 2>/dev/null) || true
}

verify() {
  log "Verificación..."
  echo "--- Puertos en escucha ---"
  ss -tlnp | grep -E ':22|:3000|:3001|:8000|:8080|:8501|:5050|:5432' || true
  echo "--- Health checks ---"
  curl -sf http://127.0.0.1:8000/health && echo " viabilidad OK"
  curl -sf http://127.0.0.1:3000/health && echo " aedmi-api-via-nginx OK"
  curl -sf -o /dev/null -w "aedmi-ui HTTP %{http_code}\n" http://127.0.0.1:3000/
  echo "--- UFW ---"
  ufw status verbose
  echo "--- DOCKER-USER ---"
  iptables -L DOCKER-USER -n -v
}

main() {
  require_root
  patch_viabilidad_compose
  patch_aedmi_compose
  patch_cfe_compose
  restart_stacks
  install_nginx
  apply_docker_user_rules
  configure_ufw
  verify
  log "Listo. Admin Streamlit: ssh -L 8501:127.0.0.1:8501 root@$(hostname -I | awk '{print $1}')"
  log "CFE dashboard: ssh -L 5050:127.0.0.1:5050 root@$(hostname -I | awk '{print $1}')"
}

main "$@"
