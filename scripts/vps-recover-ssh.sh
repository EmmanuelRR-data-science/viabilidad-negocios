#!/usr/bin/env bash
# Recuperación de acceso SSH si UFW bloqueó la conexión.
# Ejecutar desde la consola web de Hetzner (KVM), no por SSH.
set -euo pipefail

echo "[recover-ssh] Restaurando acceso SSH..."
ufw --force enable
ufw limit OpenSSH
ufw allow 8000/tcp comment 'GeoViabilidad'
ufw allow 3000/tcp comment 'AEDMI'
ufw reload
ss -tlnp | grep ':22' || systemctl restart ssh
echo "[recover-ssh] UFW actual:"
ufw status verbose
