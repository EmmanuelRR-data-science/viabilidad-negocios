#!/usr/bin/env bash
set -euo pipefail

log() { echo "[vps-fix] $*"; }

fix_after_rules() {
  local rules="/etc/ufw/after.rules"
  cp "${rules}" "${rules}.bak.$(date +%s)"
  python3 - <<'PY'
from pathlib import Path
p = Path("/etc/ufw/after.rules")
text = p.read_text()
start = "# BEGIN VPS-HARDENING DOCKER-USER"
end = "# END VPS-HARDENING DOCKER-USER"
if start in text:
    pre, rest = text.split(start, 1)
    _, post = rest.split(end, 1)
    text = pre.rstrip() + "\n\n# don't delete the 'COMMIT' line or these rules won't be processed\nCOMMIT\n"
    if post.strip():
        text += post.lstrip()
    p.write_text(text)
PY
  if ! grep -q "BEGIN VPS-HARDENING DOCKER-USER" "${rules}"; then
    cat >> "${rules}" <<'EOF'

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
  fi
  ufw reload
}

recreate_cfe() {
  log "Recreando CFE en localhost..."
  (cd /opt/cfe-dashboard && docker compose up -d)
}

clean_ufw() {
  log "Limpiando reglas UFW obsoletas..."
  for _ in $(seq 1 30); do
    num="$(ufw status numbered | grep -E '5000|5050|8501|8080|5432' | head -1 | sed -n 's/^\[\([0-9]*\)\].*/\1/p' || true)"
    [[ -n "${num}" ]] || break
    ufw --force delete "${num}" || break
  done
}

verify() {
  log "Verificación final..."
  ss -tlnp | grep -E ':3000|:3001|:8000|:8080|:8501|:5050' || true
  iptables -L DOCKER-USER -n -v | head -12
  ufw status verbose | head -18
  curl -sf http://127.0.0.1:8000/health && echo " viabilidad OK"
  curl -sf http://127.0.0.1:3000/health && echo " aedmi OK"
}

fix_after_rules
recreate_cfe
clean_ufw
verify
log "Corrección completada."
